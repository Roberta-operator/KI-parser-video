import os
import fitz  # PyMuPDF
from openai import OpenAI, AsyncOpenAI
import logging
from dotenv import load_dotenv
from typing import Tuple, Optional, List
import json
import io
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path  # Added Path import

logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

def count_tokens(text: str) -> int:
    """
    More conservative token count approximation:
    - Average English word is ~1.3 tokens
    - Special characters and spaces add extra tokens
    - Numbers and technical terms often split into multiple tokens
    """
    # Split on whitespace and punctuation
    words = text.split()
    # Count special characters and numbers which often become separate tokens
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    # More conservative estimate: words * 1.3 for average word tokenization + special characters
    return int(len(words) * 1.3) + special_chars

def chunk_text(text: str, max_tokens: int = 4000) -> List[str]:
    """Split text into chunks that fit within token limits with a more conservative approach."""
    # Split text into paragraphs
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    # Reserve tokens for system message and instructions (approximately 1000 tokens)
    effective_max_tokens = max_tokens - 1000

    for paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)
        
        # If a single paragraph is too long, split it into sentences
        if paragraph_tokens > effective_max_tokens:
            sentences = paragraph.split('. ')
            current_sentence_group = []
            current_sentence_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = count_tokens(sentence)
                
                # If adding this sentence would exceed the limit
                if current_sentence_tokens + sentence_tokens > effective_max_tokens:
                    if current_sentence_group:
                        chunks.append('. '.join(current_sentence_group) + '.')
                    current_sentence_group = [sentence]
                    current_sentence_tokens = sentence_tokens
                else:
                    current_sentence_group.append(sentence)
                    current_sentence_tokens += sentence_tokens
            
            # Add any remaining sentences
            if current_sentence_group:
                chunks.append('. '.join(current_sentence_group) + '.')
                
        # If adding the paragraph doesn't exceed limit
        elif current_length + paragraph_tokens <= effective_max_tokens:
            current_chunk.append(paragraph)
            current_length += paragraph_tokens
        # If adding paragraph would exceed limit, start a new chunk
        else:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk = [paragraph]
            current_length = paragraph_tokens

    # Add the last chunk if it exists
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks

def combine_release_notes(notes_list: List[str]) -> str:
    """Combine multiple release notes sections intelligently."""
    if not notes_list:
        return ""
        
    # Combine all notes
    combined_text = '\n\n'.join(notes_list)
    
    # Use GPT to summarize and combine the release notes
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a technical writer tasked with combining multiple sections of release notes into a coherent, non-repetitive document. Organize the information logically, remove duplicates, and ensure the final document follows a clear structure."},
                {"role": "user", "content": f"Combine these release notes sections into a single coherent document:\n\n{combined_text}"}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error combining release notes: {str(e)}")
        # Fallback to simple combination if the API call fails
        return combined_text

# Initialize a global instance of OpenAIAgent
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = OpenAIAgent()
    return _agent

async def process_document_with_openai(content: bytes, filename: str, language: str = 'en') -> str:
    """
    Process document content with OpenAI and generate release notes in the specified language
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Extract text content based on file type
        text_content = ""
        if filename.lower().endswith('.pdf'):
            # Handle PDF files using a context manager for proper cleanup
            temp_file = None
            try:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                temp_file.write(content)
                temp_file.flush()
                temp_file.close()  # Close the file before opening with PyMuPDF
                
                doc = fitz.open(temp_file.name)
                text_content = ""
                for page in doc:
                    text_content += page.get_text()
                doc.close()
            finally:
                # Clean up the temporary file
                if (temp_file and os.path.exists(temp_file.name)):
                    try:
                        os.unlink(temp_file.name)
                    except Exception as e:
                        logger.warning(f"Could not delete temporary file {temp_file.name}: {str(e)}")
        else:
            # For text files, try to decode as UTF-8 with fallback to other encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    text_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not text_content:
                raise ValueError("Could not decode file content with any supported encoding")

        # First, detect the language of the input text using GPT (using just the first chunk)
        first_chunk = text_content[:2000]  # Use first 2000 characters for language detection
        detection_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a language detection expert. Respond only with the ISO 639-1 language code of the text."},
                {"role": "user", "content": f"What is the language code of this text (respond with only the 2-letter code):\n\n{first_chunk}"}
            ],
            temperature=0,
            max_tokens=2
        )
        
        # Get the detected language code
        detected_lang = detection_response.choices[0].message.content.strip().lower()
        
        # Use detected language if no specific language was requested
        if language == 'en' and detected_lang != 'en':
            language = detected_lang
        
        # Define system message based on language
        system_messages = {
            'en': "You are a skilled technical writer specializing in creating clear and concise release notes in English.",
            'fr': "Vous êtes un rédacteur technique spécialisé dans la création de notes de version claires et concises en français.",
            'de': "Sie sind ein technischer Redakteur, der sich auf die Erstellung klarer und präziser Release Notes in deutscher Sprache spezialisiert hat.",
            'es': "Eres un redactor técnico especializado en crear notas de versión claras y concisas en español.",
            'it': "Sei un redattore tecnico specializzato nella creazione di note di rilascio chiare e concise in italiano.",
            'pt': "Você é um redator técnico especializado em criar notas de versão claras e concisas em português.",
            'nl': "U bent een technisch schrijver gespecialiseerd in het maken van heldere en beknopte releasenotities in het Nederlands.",
            'pl': "Jesteś doświadczonym redaktorem technicznym specjalizującym się w tworzeniu przejrzystych i zwięzłych notatek o wydaniu w języku polskim."
        }

        # Add language instruction to the user message
        language_instructions = {
            'en': "Write the release notes in English.",
            'fr': "Rédigez les notes de version en français.",
            'de': "Schreiben Sie die Release Notes auf Deutsch.",
            'es': "Escribe las notas de versión en español.",
            'it': "Scrivi le note di rilascio in italiano.",
            'pt': "Escreva as notas de versão em português.",
            'nl': "Schrijf de releasenotities in het Nederlands.",
            'pl': "Napisz notatkę o wydaniu w języku polskim."
        }
        
        # Use default English if language not supported
        system_message = system_messages.get(language, system_messages['en'])
        language_instruction = language_instructions.get(language, language_instructions['en'])
        
        # Split text into chunks if it's too long
        text_chunks = chunk_text(text_content)
        release_notes_chunks = []

        # Process each chunk
        for i, chunk in enumerate(text_chunks):
            chunk_instruction = f"{language_instruction}\n\nThis is part {i+1} of {len(text_chunks)}. Generate release notes from the following content:\n\n{chunk}"
            
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"{system_message} IMPORTANT: You must write ONLY in {language}. Do not use any other language. If this is not the first chunk, continue from the previous part and maintain consistency."},
                    {"role": "user", "content": chunk_instruction}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            release_notes_chunks.append(completion.choices[0].message.content)

        # Combine all chunks into a coherent document
        if len(release_notes_chunks) > 1:
            final_notes = combine_release_notes(release_notes_chunks)
        else:
            final_notes = release_notes_chunks[0]
        
        return final_notes

    except Exception as e:
        logger.error(f"Error processing document with OpenAI: {str(e)}")
        raise ValueError(f"Failed to generate release notes: {str(e)}")

class OpenAIAgent:
    def __init__(self):
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.context = ""  # Store the current content
        self.template_content = self._load_template()
        self.TEMPLATE = """
Plug&Plai Assistant is an AI assistant for Sales, Product, and Customer Success teams that answers questions about the Compleet Vendor Platform and can generate Release Notes and Release Review presentations. The answers are based exclusively on the contents of the following updated documents.

**Reference Template - Use this exact structure and style for your release notes:**
{template_content}

**Note on New Functionality (As of {date:%B %Y}):**
[Describe the latest functionality updates in a customer-focused way]

**Specific Knowledge about This Release:**
[List key points about the release, such as:]
- New integrations and system connections
- Automatic processes and synchronizations
- New capabilities and features
- Planned developments and future enhancements
- Important system details and configurations
- Key benefits and improvements

**Instructions for Release Notes Generation:**
1. Study the reference template above carefully - it shows the exact structure and style to follow
2. Use the same formatting, heading styles, and organization as shown in the template
3. When generating new release notes:
   - Follow the same sectioning and hierarchy
   - Use identical formatting for headings, bullets, and sections
   - Match the tone and level of detail
   - Keep consistent with terminology and phrasing patterns

**Release Notes Structure (Follow Template):**
- Each function or topic gets a separate point (e.g., Point 1: Integration Enhancement, Point 2: Process Automation)
- For each point:
  - "Previous State" (What was before?)
  - "New State" (What's new?)
  - "Customer Benefits"
- Clear, customer-oriented language
- When multiple transcripts are uploaded, interpret these as individual functions and list them separately

Now analyze this content and generate release notes following the template structure exactly:
{content}
"""

    def _load_template(self) -> str:
        """Load the template content from the data folder"""
        try:
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                       "data", "template.pdf")
            if not os.path.exists(template_path):
                logger.error(f"Template file not found at {template_path}")
                return ""

            success, content = self._extract_from_pdf(template_path)
            if success:
                logger.info("Successfully loaded template content")
                return content
            else:
                logger.error("Failed to load template content")
                return ""
        except Exception as e:
            logger.error(f"Error loading template: {str(e)}")
            return ""

    def extract_text_from_file(self, file_path: str) -> Tuple[bool, str]:
        """Extract text from PDF, TXT, or JSON file"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False, "File not found"

            file_ext = file_path.lower().split('.')[-1]
            
            if file_ext == 'pdf':
                return self._extract_from_pdf(file_path)
            elif file_ext == 'txt':
                return self._extract_from_txt(file_path)
            elif file_ext == 'json':
                return self._extract_from_json(file_path)
            else:
                return False, f"Unsupported file type: {file_ext}"
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            return False, f"Error processing file: {str(e)}"

    def _extract_from_pdf(self, pdf_path: str) -> Tuple[bool, str]:
        try:
            doc = fitz.open(pdf_path)
            if (doc.page_count == 0):
                logger.error(f"PDF file is empty: {pdf_path}")
                return False, "PDF file is empty"
                
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            
            if not text.strip():
                logger.warning(f"PDF file contains no text: {pdf_path}")
                return False, "PDF file contains no extractable text"
                
            return True, text
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}")
            return False, f"Error reading PDF: {str(e)}"

    def _extract_from_txt(self, txt_path: str) -> Tuple[bool, str]:
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return True, text
        except Exception as e:
            logger.error(f"Error reading TXT: {str(e)}")
            return False, f"Error reading TXT: {str(e)}"

    def _extract_from_json(self, json_path: str) -> Tuple[bool, str]:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Convert JSON to string representation
            text = json.dumps(data, indent=2)
            return True, text
        except Exception as e:
            logger.error(f"Error reading JSON: {str(e)}")
            return False, f"Error reading JSON: {str(e)}"

    def extract_text_from_memory(self, file_obj: io.BytesIO, filename: str = None) -> Tuple[bool, str]:
        """Extract text from file in memory"""
        try:
            # If filename is provided, use it to determine file type
            if filename:
                file_ext = Path(filename).suffix.lower().strip('.')
            # If no filename provided, try to get it from the file_obj
            elif hasattr(file_obj, 'name'):
                file_ext = Path(file_obj.name).suffix.lower().strip('.')
            else:
                # Default to txt if no extension can be determined
                logger.warning("No filename provided and BytesIO object has no name attribute. Defaulting to txt format.")
                file_ext = 'txt'
            
            logger.info(f"Processing file with extension: {file_ext}")
                
            if file_ext == 'pdf':
                logger.info("Extracting text from PDF")
                return self._extract_from_pdf_memory(file_obj)
            elif file_ext == 'txt':
                logger.info("Extracting text from TXT")
                return self._extract_from_txt_memory(file_obj)
            elif file_ext == 'json':
                logger.info("Extracting text from JSON")
                return self._extract_from_json_memory(file_obj)
            elif file_ext in ['mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'm4a', 'wav']:
                logger.info("Extracting text from audio/video")
                return self._extract_from_audio_video_memory(file_obj)
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return False, f"Unsupported file type: {file_ext}"
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}", exc_info=True)
            return False, f"Error processing file: {str(e)}"

    def _extract_from_pdf_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        """Extract text from PDF in memory"""
        try:
            logger.info("Starting PDF text extraction")
            # Create a temporary memory buffer for fitz
            doc = fitz.open(stream=file_obj.getvalue(), filetype="pdf")
            if doc.page_count == 0:
                logger.error("PDF file is empty")
                return False, "PDF file is empty"
            
            logger.info(f"PDF has {doc.page_count} pages")
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            
            if not text.strip():
                logger.warning("PDF file contains no text")
                return False, "PDF file contains no extractable text"
            
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return True, text
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}", exc_info=True)
            return False, f"Error reading PDF: {str(e)}"

    def _extract_from_txt_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        try:
            text = file_obj.getvalue().decode('utf-8')
            return True, text
        except Exception as e:
            logger.error(f"Error reading TXT: {str(e)}")
            return False, f"Error reading TXT: {str(e)}"

    def _extract_from_json_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        try:
            data = json.loads(file_obj.getvalue())
            # Convert JSON to string representation
            text = json.dumps(data, indent=2)
            return True, text
        except Exception as e:
            logger.error(f"Error reading JSON: {str(e)}")
            return False, f"Error reading JSON: {str(e)}"

    def _extract_from_audio_video_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        """Extract transcript from audio/video file using OpenAI's Whisper model"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.' + file_obj.name.split('.')[-1]) as temp_file:
                temp_file.write(file_obj.getvalue())
                temp_path = temp_file.name

            try:
                # Transcribe using OpenAI Whisper
                with open(temp_path, 'rb') as media_file:
                    logger.info("Starting transcription with Whisper")
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=media_file,
                        response_format="text"
                    )

                # Clean up temporary file
                os.unlink(temp_path)

                if not transcript:
                    return False, "Failed to transcribe media file"

                logger.info("Successfully transcribed media file")
                return True, transcript

            except Exception as e:
                # Clean up temporary file in case of error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                logger.error(f"Error processing media file: {str(e)}")
                return False, f"Error processing media file: {str(e)}"

        except Exception as e:
            logger.error(f"Error extracting transcript from media file: {str(e)}")
            return False, f"Error extracting transcript from media file: {str(e)}"

    def generate_release_notes(self, file_obj: io.BytesIO, filename: str = None) -> Tuple[bool, str]:
        """Generate release notes from the file content"""
        try:
            logger.info("Starting release notes generation")
            
            # Extract content from the uploaded file
            success, content = self.extract_text_from_memory(file_obj, filename)
            if not success:
                logger.error("Failed to process transcript")
                return False, "Failed to process the transcript file"

            # Set the content
            self.context = content

            # Detect language from content
            try:
                logger.info("Detecting content language")
                detection_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a language detection expert. Respond only with the ISO 639-1 language code of the text."},
                        {"role": "user", "content": f"What is the language code of this text (respond with only the 2-letter code):\n\n{content[:2000]}"}
                    ],
                    temperature=0,
                    max_tokens=2
                )
                detected_lang = detection_response.choices[0].message.content.strip().lower()
                logger.info(f"Detected language: {detected_lang}")
            except Exception as e:
                logger.error(f"Error detecting language: {str(e)}")
                detected_lang = 'en'  # Default to English if detection fails

            # Define system message based on detected language
            system_messages = {
                'en': "You are a skilled technical writer specializing in creating clear and concise release notes in English.",
                'fr': "Vous êtes un rédacteur technique spécialisé dans la création de notes de version claires et concises en français.",
                'de': "Sie sind ein technischer Redakteur, der sich auf die Erstellung klarer und präziser Release Notes in deutscher Sprache spezialisiert hat.",
                'es': "Eres un redactor técnico especializado en crear notas de versión claras y concisas en español.",
                'it': "Sei un redattore tecnico specializzato nella creazione di note di rilascio chiare e concise in italiano.",
                'pt': "Você é um redator técnico especializado em criar notas de versão claras e concisas em português.",
                'nl': "U bent een technisch schrijver gespecialiseerd in het maken van heldere en beknopte releasenotities in het Nederlands.",
                'pl': "Jesteś doświadczonym redaktorem technicznym specjalizującym się w tworzeniu przejrzystych i zwięzłych notatek o wydaniu w języku polskim."
            }

            # Add language instruction to the system prompt
            language_instructions = {
                'en': "Write the release notes in English.",
                'fr': "Rédigez les notes de version en français.",
                'de': "Schreiben Sie die Release Notes auf Deutsch.",
                'es': "Escribe las notas de versión en español.",
                'it': "Scrivi le note di rilascio in italiano.",
                'pt': "Escreva as notas de versão em português.",
                'nl': "Schrijf de releasenotities in het Nederlands.",
                'pl': "Napisz notatkę o wydaniu w języku polskim."
            }

            # Use detected language or default to English if not supported
            system_message = system_messages.get(detected_lang, system_messages['en'])
            language_instruction = language_instructions.get(detected_lang, language_instructions['en'])

            system_prompt = self.TEMPLATE.format(
                template_content=self.template_content,
                content=self.context,
                date=datetime.now()
            )

            # Add language-specific instructions
            system_prompt = f"{system_message}\n\n{language_instruction}\n\n{system_prompt}"

            try:
                logger.info(f"Calling OpenAI API with detected language: {detected_lang}")
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Generate release notes from the learned content"}
                    ],
                    temperature=0.7,
                    presence_penalty=0.1,
                    frequency_penalty=0.1,
                    max_tokens=2000
                )
                
                logger.info("Successfully generated release notes")
                return True, response.choices[0].message.content
                
            except Exception as api_error:
                logger.error(f"OpenAI API error: {str(api_error)}")
                return False, f"OpenAI API error: {str(api_error)}"
                
        except Exception as e:
            logger.error(f"Unexpected error in generate_release_notes: {str(e)}")
            return False, f"Error generating release notes: {str(e)}"

    def _chunk_content(self, content: str, max_tokens: int = 4000) -> list[str]:
        """Split content into chunks that fit within token limits"""
        # Rough estimate: 1 token ≈ 4 characters
        chunk_size = max_tokens * 4
        chunks = []
        
        # Split content into paragraphs
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + '\n\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    async def _process_with_timeout(self, coroutine, timeout_seconds: int = 180) -> Tuple[bool, str]:
        """Execute a coroutine with timeout"""
        try:
            return await asyncio.wait_for(coroutine, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"Operation timed out after {timeout_seconds} seconds")
            return False, f"Operation timed out after {timeout_seconds} seconds. Please try with a smaller file or try again later."
            
    async def generate_release_notes_async(self, file_obj: io.BytesIO, filename: str = None, timeout_seconds: int = 180) -> Tuple[bool, str]:
        """Generate release notes from the file content asynchronously with timeout"""
        return await self._process_with_timeout(
            self._generate_release_notes_internal(file_obj, filename),
            timeout_seconds
        )
        
    async def _generate_release_notes_internal(self, file_obj: io.BytesIO, filename: str = None) -> Tuple[bool, str]:
        """Internal method for generating release notes"""
        logger.info("Starting async release notes generation")
        
        try:
            # Extract content from the uploaded file
            success, content = self.extract_text_from_memory(file_obj, filename)
            if not success:
                logger.error("Failed to process transcript")
                return False, "Failed to process the transcript file"

            # Detect language from content
            try:
                logger.info("Detecting content language")
                detection_response = await self.async_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a language detection expert. Respond only with the ISO 639-1 language code of the text."},
                        {"role": "user", "content": f"What is the language code of this text (respond with only the 2-letter code):\n\n{content[:2000]}"}
                    ],
                    temperature=0,
                    max_tokens=2
                )
                detected_lang = detection_response.choices[0].message.content.strip().lower()
                logger.info(f"Detected language: {detected_lang}")
            except Exception as e:
                logger.error(f"Error detecting language: {str(e)}")
                detected_lang = 'en'  # Default to English if detection fails

            # Define system message based on detected language
            system_messages = {
                'en': "You are a skilled technical writer specializing in creating clear and concise release notes in English.",
                'fr': "Vous êtes un rédacteur technique spécialisé dans la création de notes de version claires et concises en français.",
                'de': "Sie sind ein technischer Redakteur, der sich auf die Erstellung klarer und präziser Release Notes in deutscher Sprache spezialisiert hat.",
                'es': "Eres un redactor técnico especializado en crear notas de versión claras y concisas en español.",
                'it': "Sei un redattore tecnico specializzato nella creazione di note di rilascio chiare e concise in italiano.",
                'pt': "Você é um redator técnico especializado em criar notas de versão claras e concisas em português.",
                'nl': "U bent een technisch schrijver gespecialiseerd in het maken van heldere en beknopte releasenotities in het Nederlands.",
                'pl': "Jesteś doświadczonym redaktorem technicznym specjalizującym się w tworzeniu przejrzystych i zwięzłych notatek o wydaniu w języku polskim."
            }

            # Add language instruction to the system prompt
            language_instructions = {
                'en': "Write the release notes in English.",
                'fr': "Rédigez les notes de version en français.",
                'de': "Schreiben Sie die Release Notes auf Deutsch.",
                'es': "Escribe las notas de versión en español.",
                'it': "Scrivi le note di rilascio in italiano.",
                'pt': "Escreva as notas de versão em português.",
                'nl': "Schrijf de releasenotities in het Nederlands.",
                'pl': "Napisz notatkę o wydaniu w języku polskim."
            }

            # Use detected language or default to English if not supported
            system_message = system_messages.get(detected_lang, system_messages['en'])
            language_instruction = language_instructions.get(detected_lang, language_instructions['en'])

            # Set the content and chunk it if necessary
            self.context = content
            content_chunks = self._chunk_content(content)
            
            # If content needs to be chunked
            if len(content_chunks) > 1:
                all_notes = []
                for i, chunk in enumerate(content_chunks):
                    try:
                        system_prompt = self.TEMPLATE.format(
                            template_content=self.template_content,
                            content=chunk,
                            date=datetime.now()
                        )
                        # Add language-specific instructions
                        system_prompt = f"{system_message}\n\n{language_instruction}\n\n{system_prompt}"
                        
                        logger.info(f"Processing chunk {i+1} of {len(content_chunks)} in {detected_lang}")
                        response = await self.async_client.chat.completions.create(
                            model="gpt-4-turbo-preview",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"Generate release notes for part {i+1} of {len(content_chunks)}"}
                            ],
                            temperature=0.7,
                            presence_penalty=0.1,
                            frequency_penalty=0.1,
                            max_tokens=1000
                        )
                        all_notes.append(response.choices[0].message.content)
                    except Exception as chunk_error:
                        logger.error(f"Error processing chunk {i+1}: {str(chunk_error)}")
                        continue  # Continue with next chunk if one fails

                if not all_notes:
                    return False, "Failed to process any content chunks successfully"

                try:
                    # Combine all chunks
                    final_prompt = self.TEMPLATE.format(
                        template_content=self.template_content,
                        content="\n\n".join(all_notes),
                        date=datetime.now()
                    )
                    # Add language-specific instructions for final combination
                    final_prompt = f"{system_message}\n\n{language_instruction}\n\n{final_prompt}"
                    
                    # Final pass to combine and refine
                    response = await self.async_client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {"role": "system", "content": final_prompt},
                            {"role": "user", "content": "Combine and refine these release notes into a single coherent document"}
                        ],
                        temperature=0.7,
                        presence_penalty=0.1,
                        frequency_penalty=0.1,
                        max_tokens=2000
                    )
                    logger.info("Successfully generated combined release notes")
                    return True, response.choices[0].message.content
                except Exception as combine_error:
                    logger.error(f"Error combining release notes: {str(combine_error)}")
                    # If combination fails, return the concatenated chunks
                    return True, "\n\n".join(all_notes)
                    
            else:
                # Process single chunk with language detection
                try:
                    system_prompt = self.TEMPLATE.format(
                        template_content=self.template_content,
                        content=self.context,
                        date=datetime.now()
                    )
                    # Add language-specific instructions
                    system_prompt = f"{system_message}\n\n{language_instruction}\n\n{system_prompt}"

                    logger.info(f"Calling OpenAI API asynchronously with detected language: {detected_lang}")
                    response = await self.async_client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": "Generate release notes from the learned content"}
                        ],
                        temperature=0.7,
                        presence_penalty=0.1,
                        frequency_penalty=0.1,
                        max_tokens=2000
                    )
                    logger.info("Successfully generated release notes")
                    return True, response.choices[0].message.content
                except Exception as api_error:
                    logger.error(f"OpenAI API error: {str(api_error)}")
                    return False, f"OpenAI API error: {str(api_error)}"
                    
        except Exception as e:
            logger.error(f"Unexpected error in generate_release_notes_async: {str(e)}")
            return False, f"Error generating release notes: {str(e)}"
