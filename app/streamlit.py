import streamlit as st
import requests
import logging
import io
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import Optional
import time

logger = logging.getLogger(__name__)

# Constants
API_URL = "http://localhost:8000"
MAX_FILE_SIZE_MB = {
    'document': 10,  # Keep 10MB limit for documents
    'media': 100     # 100MB limit for media files
}

# Configure page settings
st.set_page_config(
    page_title="Release Notes Generator",
    page_icon="📝",
    layout="wide"
)

# Add custom CSS to center content
st.markdown(
    """
    <style>
    .main-content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
        text-align: center;
    }
    .stButton > button {
        display: block !important;
        margin: 0 auto !important;
    }
    .centered-text {
        text-align: center !important;
    }
    .release-notes-container {
        width: 80%;
        margin: 0 auto;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Configure requests session with retry logic
def create_requests_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def handle_api_request(method, endpoint, **kwargs):
    """Handle API requests with proper error handling and retry logic"""
    session = create_requests_session()
    try:
        kwargs['timeout'] = 90  # 90 seconds timeout for generation
        response = session.request(
            method,
            f"http://127.0.0.1:8000{endpoint}",
            **kwargs
        )
        response.raise_for_status()
        
        if response.content:
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON from response: {response.content}")
                st.error("Received invalid response from server. Please try again.")
                return None
        else:
            logger.error("Received empty response from server")
            st.error("Received empty response from server. Please try again.")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out for endpoint: {endpoint}")
        st.error("The release notes generation is taking longer than expected. Please try again or try with a smaller file.")
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection failed for endpoint: {endpoint}")
        st.error("Cannot connect to the server. Please check if the FastAPI backend is running (uvicorn app.main:app --reload)")
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        st.error(f"An error occurred: {str(e)}")
    return None

def display_release_notes(response):
    """Display the generated release notes and download buttons"""
    with st.container():
        # Add some vertical spacing before the content
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Create a container with proper styling
        st.markdown(
            """
            <style>
            .release-notes {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            .release-notes h1, .release-notes h2, .release-notes h3 {
                text-align: center;
                margin: 1.5em 0 1em 0;
            }
            .release-notes ul, .release-notes ol {
                margin-left: 2em;
                margin-bottom: 1em;
            }
            .release-notes p {
                margin-bottom: 1em;
            }
            .release-notes em {
                color: #666;
            }
            .download-section {
                text-align: center;
                margin-top: 2em;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        # Format the content for better markdown rendering
        generated_text = response["content"]
        
        # Process the markdown content
        formatted_text = "<div class='release-notes'>"
        current_list = []
        in_list = False
        
        for line in generated_text.split('\n'):
            line = line.strip()
            if line:
                # Handle headers
                if line.startswith('**') and line.endswith('**'):
                    if in_list:
                        formatted_text += "<ul>" + "\n".join(current_list) + "</ul>"
                        current_list = []
                        in_list = False
                    line = f"<h2>{line.strip('**')}</h2>"
                # Handle bullet points
                elif line.startswith('- '):
                    in_list = True
                    current_list.append(f"<li>{line[2:]}</li>")
                    continue
                # Handle emphasized text
                elif line.startswith('*') and line.endswith('*'):
                    line = f"<em>{line.strip('*')}</em>"
                else:
                    if in_list:
                        formatted_text += "<ul>" + "\n".join(current_list) + "</ul>"
                        current_list = []
                        in_list = False
                    line = f"<p>{line}</p>"
                
                formatted_text += line + "\n"
        
        # Add any remaining list items
        if current_list:
            formatted_text += "<ul>" + "\n".join(current_list) + "</ul>"
        
        formatted_text += "</div>"
        
        # Display the formatted content
        st.markdown(formatted_text, unsafe_allow_html=True)
        
        # Add download buttons section
        st.markdown("<div class='download-section'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                from reportlab.lib.units import inch
                from io import BytesIO
                
                # Create PDF buffer
                pdf_buffer = BytesIO()
                
                # Create the PDF document
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=A4,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72
                )
                
                # Create styles
                styles = getSampleStyleSheet()
                title_style = styles['Title']
                normal_style = styles['Normal']
                
                # Prepare the story (content)
                story = []
                
                # Add title
                story.append(Paragraph("Release Notes", title_style))
                story.append(Spacer(1, 12))
                
                # Process and add content with proper spacing
                for line in generated_text.split('\n'):
                    if line.strip():  # Skip empty lines
                        # Check if line is a header
                        if line.startswith('#') or line.startswith('Point'):
                            style = styles['Heading1']
                            # Add extra spacing before headers
                            story.append(Spacer(1, 12))
                        else:
                            style = normal_style
                        
                        story.append(Paragraph(line, style))
                        story.append(Spacer(1, 6))
                
                # Build the PDF
                doc.build(story)
                pdf_buffer.seek(0)
                
                # Offer download with custom styling
                st.download_button(
                    label="Download as PDF",
                    data=pdf_buffer,
                    file_name="release_notes.pdf",
                    mime="application/pdf",
                    key="pdf_download"
                )
                
            except Exception as e:
                st.error(f"Error creating PDF: {str(e)}")
                logger.error(f"PDF generation error: {str(e)}")
        
        with col2:
            st.download_button(
                label="Download as TXT",
                data=generated_text,
                file_name="release_notes.txt",
                mime="text/plain",
                key="txt_download"
            )
        st.markdown("</div>", unsafe_allow_html=True)

def check_file_size(file, file_type='document') -> Optional[str]:
    """Check if file size is within limits based on file type"""
    limit = MAX_FILE_SIZE_MB['media'] if file_type == 'media' else MAX_FILE_SIZE_MB['document']
    if file.size > limit * 1024 * 1024:
        return f"File size exceeds {limit}MB limit. Please upload a smaller file."
    return None

def format_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}GB"

def display_processing_status(total_files: int):
    """Create and return enhanced progress tracking elements"""
    # Create a container for all progress elements
    progress_container = st.container()
    with progress_container:
        # Add a processing header
        st.markdown("#### 🔄 Processing Status")
        
        # Create columns for different status elements
        col1, col2 = st.columns(2)
        
        with col1:
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        with col2:
            # Create metrics container
            metrics_container = st.container()
            with metrics_container:
                time_remaining = st.empty()
    
    return progress_bar, status_text, time_remaining

def estimate_remaining_time(start_time: float, current_file: int, total_files: int) -> str:
    """Calculate and format estimated remaining time with enhanced formatting"""
    elapsed_time = time.time() - start_time
    avg_time_per_file = elapsed_time / current_file if current_file > 0 else 0
    remaining_files = total_files - current_file
    estimated_remaining = avg_time_per_file * remaining_files
    
    # Format the time in a more readable way
    if estimated_remaining < 60:
        return f"⏱️ About {max(1, int(estimated_remaining))} seconds remaining"
    elif estimated_remaining < 3600:
        minutes = int(estimated_remaining // 60)
        seconds = int(estimated_remaining % 60)
        return f"⏱️ About {minutes}m {seconds}s remaining"
    else:
        hours = int(estimated_remaining // 3600)
        minutes = int((estimated_remaining % 3600) // 60)
        return f"⏱️ About {hours}h {minutes}m remaining"

def main():
    # Main header with description
    st.title("📝 Release Notes Generator")
    st.markdown("""
    ### Transform your documents and videos into professional release notes
    Upload your files below and let AI help you generate clear, organized release notes.
    """)
    
    # Create a container for file upload sections
    with st.container():
        # Create tabs for different file types with icons
        doc_tab, media_tab = st.tabs(["📄 Documents", "🎥 Media Files"])

        with doc_tab:
            st.markdown("""
            #### Document Processing
            Upload your documents to generate detailed release notes. Perfect for changelogs, updates, and documentation.
            """)
            st.info(f"""
            **Supported document types**:
            - 📄 PDF files
            - 📝 TXT files
            - 🔧 JSON files
            
            Maximum file size: **{MAX_FILE_SIZE_MB['document']}MB**
            """)
            
            doc_file = st.file_uploader(
                "Drop your document here or click to browse",
                type=['txt', 'pdf', 'json'],
                accept_multiple_files=False
            )
            
            if doc_file:
                st.markdown("---")
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**Selected file**: {doc_file.name}")
                    with col2:
                        size = format_size(doc_file.size)
                        if (error := check_file_size(doc_file)) is None:
                            st.markdown(f"**Size**: ✅ {size}")
                    with col3:
                        if error is None:
                            if st.button("🚀 Generate Notes", key="doc_button", use_container_width=True):
                                try:
                                    # ...existing code for document processing...
                                    start_time = time.time()
                                    progress_bar, status_text, time_remaining = display_processing_status(1)
                                    
                                    # Update progress indicators
                                    progress_bar.progress(0.3)
                                    status_text.text(f"Processing {doc_file.name}...")
                                      # Process file
                                    files = {"file": (doc_file.name, doc_file.getvalue(), doc_file.type)}
                                    
                                    with st.spinner(f"Generating release notes for {doc_file.name}..."):
                                        response = handle_api_request(
                                            "POST",
                                            "/api/generate-release-notes",
                                            files=files
                                        )
                                        
                                        if response and response.get("success"):
                                            progress_bar.progress(1.0)
                                            status_text.text("Processing complete!")
                                            time_remaining.text(f"Total time: {int(time.time() - start_time)}s")
                                            st.success(f"✅ Successfully processed {doc_file.name}")
                                            display_release_notes(response)
                                        else:
                                            error_msg = response.get("message", "Unknown error") if response else "Failed to get response"
                                            st.error(f"Failed to process {doc_file.name}: {error_msg}")
                                except Exception as e:
                                    st.error(f"❌ Error processing {doc_file.name}: {str(e)}")
                                    logger.error(f"Error processing {doc_file.name}: {str(e)}")
                                finally:
                                    # Clean up progress display after a delay
                                    time.sleep(2)
                                    progress_bar.empty()
                                    status_text.empty()
                                    time_remaining.empty()
                        else:
                            st.error(f"❌ {size} - {error}")

        with media_tab:
            st.markdown("""
            #### Media Processing
            Upload your video files to extract content and generate release notes. Perfect for presentations and demos.
            """)
            st.info(f"""
            **Supported video formats**:
            - 🎥 MP4, MPEG
            - 📹 M4V, MOV
            - 🎬 AVI, WMV
            
            Maximum file size: **{MAX_FILE_SIZE_MB['media']}MB**
            """)
            
            media_file = st.file_uploader(
                "Drop your video here or click to browse",
                type=['mp4', 'mpeg', 'm4v', 'mov', 'avi', 'wmv'],
                accept_multiple_files=False
            )
            
            if media_file:
                st.markdown("---")
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(f"**Selected file**: {media_file.name}")
                    with col2:
                        size = format_size(media_file.size)
                        if (error := check_file_size(media_file, 'media')) is None:
                            st.markdown(f"**Size**: ✅ {size}")
                    with col3:
                        if error is None:
                            if st.button("🚀 Generate Notes", key="media_button", use_container_width=True):
                                try:
                                    # ...existing code for media processing...
                                    start_time = time.time()
                                    progress_bar, status_text, time_remaining = display_processing_status(1)
                                    
                                    # Update progress indicators
                                    progress_bar.progress(0.3)
                                    status_text.text(f"Processing {media_file.name}...")
                                    
                                    # Process file
                                    files = {"file": (media_file.name, media_file.getvalue(), media_file.type)}
                                    
                                    with st.spinner(f"Generating release notes for {media_file.name}..."):
                                        response = handle_api_request(
                                            "POST",
                                            "/api/upload-video",
                                            files=files
                                        )
                                        
                                        if response:
                                            progress_bar.progress(1.0)
                                            status_text.text("Processing complete!")
                                            time_remaining.text(f"Total time: {int(time.time() - start_time)}s")
                                            st.success(f"✅ Successfully processed {media_file.name}")
                                            
                                            # Display results in expandable sections
                                            with st.expander("📝 Video Transcript", expanded=False):
                                                st.text_area("Full Transcript", response["transcript"], height=200)
                                            
                                            st.markdown("### 📋 Generated Release Notes")
                                            display_release_notes({"content": response["release_notes"]})
                                        else:
                                            error_msg = response.get("detail", "Unknown error") if response else "Failed to get response"
                                            st.error(f"Failed to process {media_file.name}: {error_msg}")
                                except Exception as e:
                                    st.error(f"❌ Error processing {media_file.name}: {str(e)}")
                                    logger.error(f"Error processing {media_file.name}: {str(e)}")
                                finally:
                                    # Clean up progress display after a delay
                                    time.sleep(2)
                                    progress_bar.empty()
                                    status_text.empty()
                                    time_remaining.empty()
                        else:
                            st.error(f"❌ {size} - {error}")

    # Add a footer with information
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <p><small>🛠️ Release Notes Generator | Process your documents and videos efficiently</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
