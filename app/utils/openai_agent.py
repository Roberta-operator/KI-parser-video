import os
import fitz  # PyMuPDF
from openai import OpenAI
import logging
from dotenv import load_dotenv
from typing import Tuple
import json
import io
import asyncio
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Initialize a global instance of OpenAIAgent
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = OpenAIAgent()
    return _agent

async def process_document_with_openai(content: bytes, filename: str) -> str:
    """Process a document with OpenAI and return generated release notes."""
    try:
        # Create a BytesIO object from the content
        file_obj = io.BytesIO(content)
        file_obj.name = filename  # Set the filename for type detection
        
        # Get the OpenAI agent instance
        agent = get_agent()
        
        # Generate release notes
        success, result = await agent.generate_release_notes_async(file_obj)
        
        if not success:
            raise Exception(result)
            
        return result
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise Exception(f"Failed to process document: {str(e)}")

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

**Note on New Functionality (As of April 2025):**
Borrowers can mark candidates as "hired" in compleet Vendor. This currently only affects reports; service providers do not yet receive notifications.

**Specific Knowledge about Release Nova from Team Mars:**
- Integration of shift planning with the Vendor Management System (VMS)
- Automatic synchronization for assignment terminations: Employee removal in Vendor automatically removes them from shift planning
- Ability to create personnel requests directly from shift planning for open requirements
- Planned development: automatic synchronization of booked employees into shift planning
- Compliance Monitor contains multiple documents per staffing provider (up to 4-5) such as temporary employment permits, professional association certificates, health insurance certificates
- Some providers are intentionally shown without documents to demonstrate different scenarios in the system
- Benefits: higher data consistency, time savings, process reliability, transparency in document status

**Instructions for Release Notes Generation:**
1. Study the reference template above carefully - it shows the exact structure and style to follow
2. Use the same formatting, heading styles, and organization as shown in the template
3. When generating new release notes:
   - Follow the same sectioning and hierarchy
   - Use identical formatting for headings, bullets, and sections
   - Match the tone and level of detail
   - Keep consistent with terminology and phrasing patterns

**Release Notes Structure (Follow Template):**
- Each function or topic gets a separate point (e.g., Point 1: Shift Planning Improvement, Point 2: Candidate Profile Enhancement)
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
            if doc.page_count == 0:
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

    def extract_text_from_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        """Extract text from file in memory"""
        try:
            file_ext = file_obj.name.lower().split('.')[-1]
            
            if file_ext == 'pdf':
                return self._extract_from_pdf_memory(file_obj)
            elif file_ext == 'txt':
                return self._extract_from_txt_memory(file_obj)
            elif file_ext == 'json':
                return self._extract_from_json_memory(file_obj)
            else:
                return False, f"Unsupported file type: {file_ext}"
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            return False, f"Error processing file: {str(e)}"

    def _extract_from_pdf_memory(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        try:
            # Create a temporary memory buffer for fitz
            doc = fitz.open(stream=file_obj.getvalue(), filetype="pdf")
            if doc.page_count == 0:
                logger.error("PDF file is empty")
                return False, "PDF file is empty"
                
            text = "\n".join([page.get_text() for page in doc])
            doc.close()
            
            if not text.strip():
                logger.warning("PDF file contains no text")
                return False, "PDF file contains no extractable text"
                
            return True, text
        except Exception as e:
            logger.error(f"Error reading PDF: {str(e)}")
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

    def generate_release_notes(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        """Generate release notes from the file content"""
        try:
            logger.info("Starting release notes generation")
            
            # Extract content from the uploaded file
            success, content = self.extract_text_from_memory(file_obj)
            if not success:
                logger.error("Failed to process transcript")
                return False, "Failed to process the transcript file"

            # Set the content
            self.context = content

            system_prompt = self.TEMPLATE.format(
                template_content=self.template_content,
                content=self.context
            )

            try:
                logger.info("Calling OpenAI API")
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",  # Using the latest available GPT-4 model
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Generate release notes from the learned content"}
                    ],
                    temperature=0.7,
                    presence_penalty=0.1,  # Improves creativity while staying on topic
                    frequency_penalty=0.1,  # Reduces repetition
                    max_tokens=2000  # Ensures comprehensive release notes
                )
                
                logger.info("Successfully generated release notes")
                return True, response.choices[0].message.content
                
            except Exception as api_error:
                logger.error(f"OpenAI API error: {str(api_error)}")
                return False, f"OpenAI API error: {str(api_error)}"
                
        except Exception as e:
            logger.error(f"Unexpected error in generate_release_notes: {str(e)}")
            return False, f"Error generating release notes: {str(e)}"

    async def generate_release_notes_async(self, file_obj: io.BytesIO) -> Tuple[bool, str]:
        """Generate release notes from the file content asynchronously"""
        try:
            logger.info("Starting async release notes generation")
            
            # Extract content from the uploaded file
            success, content = self.extract_text_from_memory(file_obj)
            if not success:
                logger.error("Failed to process transcript")
                return False, "Failed to process the transcript file"

            # Set the content
            self.context = content

            system_prompt = self.TEMPLATE.format(
                template_content=self.template_content,
                content=self.context
            )

            try:
                logger.info("Calling OpenAI API asynchronously")
                response = await self.async_client.chat.completions.create(
                    model="gpt-4-turbo-preview",  # Using the latest available GPT-4 model
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Generate release notes from the learned content"}
                    ],
                    temperature=0.7,
                    presence_penalty=0.1,  # Improves creativity while staying on topic
                    frequency_penalty=0.1,  # Reduces repetition
                    max_tokens=2000  # Ensures comprehensive release notes
                )
                
                logger.info("Successfully generated release notes")
                return True, response.choices[0].message.content
                
            except Exception as api_error:
                logger.error(f"OpenAI API error: {str(api_error)}")
                return False, f"OpenAI API error: {str(api_error)}"
                
        except Exception as e:
            logger.error(f"Unexpected error in generate_release_notes_async: {str(e)}")
            return False, f"Error generating release notes: {str(e)}"
