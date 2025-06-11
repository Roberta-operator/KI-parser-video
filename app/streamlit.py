import streamlit as st
import requests
import logging
import io
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import Optional
import time

# The backend is now deployed at https://ki-parser-video.fly.dev
logger = logging.getLogger(__name__)

# Constants
API_URL = "https://ki-parser-video.fly.dev"
MAX_FILE_SIZE_MB = {
    'document': 100,  # 100MB limit for documents
    'media': 1000     # 1000MB limit for media files
}

# Configure page settings
st.set_page_config(
    page_title="Release Notes Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide sidebar by default
)

# Add custom CSS
st.markdown("""
<style>
/* Reset and container styling */
.block-container {
    padding: 2rem !important;
    max-width: none !important;
}
.element-container {
    width: 800px !important;
    margin: 0 !important;
}
div[data-testid="column"] {
    width: fit-content !important;
    flex: none !important;
}
div[data-testid="stVerticalBlock"] > div {
    width: 800px !important;
    margin-left: 0 !important;
}

/* Upload button styling */
.stUploadButton > div {
    width: 800px !important;
}
.stUploadButton button {
    width: 100% !important;
}

/* Generate button styling */
.stButton > button {
    background-color: #2E86C1 !important;
    color: white !important;
    border-radius: 10px !important;
    padding: 0.5rem 2rem !important;
    font-weight: bold !important;
    border: none !important;
    transition: all 0.3s ease !important;
    width: 300px !important;
    margin: 0 auto !important;
    display: block !important;
}
.stButton > button:hover {
    background-color: #1A5276 !important;
    transform: translateY(-2px);
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* Progress bar */
.stProgress > div {
    width: 800px !important;
    margin-left: 0 !important;
}
.stProgress > div > div {
    background-color: #2ECC71 !important;
}

/* Stats box */
.metrics-container, .stats-box {
    background: linear-gradient(135deg, #1A5276 0%, #2E86C1 100%) !important;
    width: 800px !important;
    padding: 1.5rem !important;
    border-radius: 10px !important;
    color: white !important;
    margin: 1rem 0 !important;
}
.metrics-title, .stats-title {
    font-size: 1.2rem !important;
    font-weight: bold !important;
}
.metrics-value, .stats-value {
    color: #7DCEA0 !important;
    font-size: 1.1rem !important;
}

/* Content container */
.content-container {
    width: 800px !important;
    background: white !important;
    padding: 2rem !important;
    border-radius: 10px !important;
    margin: 1rem 0 !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
}

/* Release notes and transcript */
.release-notes {
    width: 100% !important;
    margin: 0 !important;
    line-height: 1.8 !important;
    color: #2C3E50 !important;
    font-size: 1.1rem !important;
}
.release-notes h1, .release-notes h2, .release-notes h3 {
    color: #2E86C1 !important;
    margin: 1.5em 0 0.8em !important;
    font-weight: bold !important;
    font-size: 1.3rem !important;
}
.release-notes ul, .release-notes ol {
    margin-left: 2em !important;
    margin-bottom: 1.5em !important;
    color: #2C3E50 !important;
}
.release-notes p {
    margin-bottom: 1.2em !important;
    color: #2C3E50 !important;
}
.release-notes em {
    color: #27AE60 !important;
    font-weight: 500 !important;
}
.release-notes li {
    margin-bottom: 0.5em !important;
    color: #2C3E50 !important;
}
.release-notes strong {
    color: #2C3E50 !important;
    font-weight: bold !important;
    display: block !important;
    margin-top: 1.2em !important;
}

/* Download section */
.download-section {
    width: 800px !important;
    display: flex !important;
    gap: 1rem !important;
    margin: 2rem 0 !important;
    justify-content: flex-start !important;
}
.download-section .stButton > button {
    width: auto !important;
    display: inline-block !important;
}

/* Success/Error messages */
.stSuccess, .stError {
    width: 800px !important;
    margin-left: 0 !important;
}

/* Tabs */
div[data-testid="stHorizontalBlock"] {
    width: 800px !important;
}

/* Text area styling */
.stTextArea > div {
    width: 800px !important;
}
.stTextArea textarea {
    color: #2C3E50 !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
    background: #f8f9fa !important;
}

/* Expander styling */
.streamlit-expander {
    width: 800px !important;
    border-radius: 10px !important;
    border: 1px solid #e0e0e0 !important;
    margin: 1rem 0 !important;
}
</style>
""", unsafe_allow_html=True)

# Configure requests session with retry logic
def create_requests_session():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,  # number of retries
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        allowed_methods=["HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS", "TRACE"],
        backoff_factor=1  # factor to apply between attempts
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def handle_api_request(method, endpoint, **kwargs):
    """Handle API requests with proper error handling and retry logic"""
    try:
        session = create_requests_session()
        url = f"{API_URL}{endpoint}"
        response = session.request(method, url, **kwargs)
        
        if response.status_code == 404:
            st.error("⚠️ The server endpoint was not found. Please check if the service is available.")
            return None
        elif response.status_code in [500, 502, 503, 504]:
            st.error("⚠️ The server is currently experiencing issues. Please try again later.")
            return None
        elif response.status_code != 200:
            st.error(f"⚠️ Error: {response.status_code} - {response.text}")
            return None

        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Could not connect to the server. Please check your internet connection or try again later.")
        return None
    except requests.exceptions.Timeout:
        st.error("⚠️ The request timed out. Please try again.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ An error occurred: {str(e)}")
        return None
    except Exception as e:
        st.error(f"⚠️ Unexpected error: {str(e)}")
        return None

from typing import Optional

def generate_descriptive_filename(response, input_files: Optional[list] = None) -> str:
    """Generate a descriptive filename for release notes based on content and input files.
    
    Args:
        response: The response containing generated release notes (can be str or dict)
        input_files (list, optional): List of input files used to generate notes
        
    Returns:
        str: A descriptive filename (without extension)
    """
    import re
    import json
    from datetime import datetime
    from pathlib import Path

    # Extract the content from response (handle both dict and string)
    if isinstance(response, dict):
        generated_text = response.get('content', '')
    elif isinstance(response, str):
        # Try to parse as JSON first
        try:
            response_dict = json.loads(response)
            generated_text = response_dict.get('content', response)
        except json.JSONDecodeError:
            generated_text = response
    else:
        generated_text = str(response)
    
    # Extract version if present in content (common patterns)
    version_match = re.search(r'[vV]ersion\s+(\d+\.\d+\.\d+|\d+\.\d+|\d+)|v(\d+\.\d+\.\d+|\d+\.\d+|\d+)', generated_text)
    if version_match:
        version = version_match.group(1) or version_match.group(2)
        version = f"v{version.strip()}" if not version.startswith('v') else version
    else:
        version = 'v1.0.0'
    
    # Add date
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Base filename
    base = f"release_notes_{version}_{date_str}"
    
    # Handle input files part
    if input_files and isinstance(input_files, list):
        # Clean filenames and get base names
        clean_names = []
        for f in input_files:
            if hasattr(f, 'name'):  # Handle UploadedFile objects
                name = Path(f.name).stem
            else:  # Handle string paths
                name = Path(str(f)).stem
            # Clean the name (remove special chars, spaces to underscores)
            clean_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
            if clean_name:
                clean_names.append(clean_name)
        
        if len(clean_names) == 1:
            base += f"_{clean_names[0]}"
        elif len(clean_names) == 2:
            base += f"_{clean_names[0]}_{clean_names[1]}"
        elif len(clean_names) > 2:
            base += f"_{clean_names[0]}_{clean_names[1]}_and_{len(clean_names)-2}_more"
    
    return base

def generate_pdf(generated_text):
    """Generate a PDF file from the release notes text."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch
    from io import BytesIO
    
    # Create PDF buffer
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Release Notes", styles['Title']),
        Spacer(1, 12)
    ]
    
    for line in generated_text.split('\n'):
        if line.strip():
            style = styles['Heading1'] if line.startswith('#') or line.startswith('Point') else styles['Normal']
            story.append(Paragraph(line, style))
            story.append(Spacer(1, 6))
    
    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer

def display_release_notes(response, input_files=None):
    """Display the generated release notes and download buttons"""
    import json
    
    # Handle JSON responses
    if isinstance(response, dict):
        generated_text = response.get('content', '')
    elif isinstance(response, str):
        try:
            response_dict = json.loads(response)
            generated_text = response_dict.get('content', response)
        except json.JSONDecodeError:
            generated_text = response
    else:
        generated_text = str(response)
    
    # Display the generated text
    st.markdown("### Generated Release Notes:")
    st.write(generated_text)
    
    # Generate descriptive filename base
    filename_base = generate_descriptive_filename(response, input_files)
    
    # Create PDF download button
    try:
        with st.spinner("Converting to PDF..."):
            pdf_buffer = generate_pdf(generated_text)
            st.download_button(
                label="Download as PDF",
                data=pdf_buffer,
                file_name=f"{filename_base}.pdf",
                mime="application/pdf",
                key="pdf_download"
            )
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
    
    # Create TXT download button
    try:
        # Use the processed text for TXT download
        txt_buffer = generated_text.encode()
        st.download_button(
            label="Download as TXT",
            data=txt_buffer,
            file_name=f"{filename_base}.txt",
            mime="text/plain",
            key="txt_download"
        )
    except Exception as e:
        st.error(f"Error creating TXT download: {str(e)}")

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
        # Style for status box
        st.markdown("""
        <div style="width: 800px; margin-bottom: 20px;">
            <h4 style="margin-bottom: 10px;">🔄 Processing Status</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Progress bar
        progress_bar = st.progress(0)
        
        # Status text
        status_text = st.empty()
        
        # Time remaining
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
    st.markdown("""
    <h1 style='margin-bottom: 1rem; font-size: 2.5em;'>📝 Release Notes Generator</h1>
    <h3 style='margin-bottom: 2rem; color: #666; font-weight: normal;'>Transform your documents and videos into professional release notes</h3>
    """, unsafe_allow_html=True)

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

            doc_files = st.file_uploader(
                "Drop your documents here or click to browse",
                type=['txt', 'pdf', 'json'],
                accept_multiple_files=True
            )

            if doc_files:
                st.markdown("---")
                with st.container():
                    for doc_file in doc_files:
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**Selected file**: {doc_file.name}")
                        with col2:
                            size = format_size(doc_file.size)
                            if (error := check_file_size(doc_file)) is None:
                                st.markdown(f"**Size**: ✅ {size}")
                        with col3:
                            if error is None:
                                st.markdown("**Status**: Ready to process")

                    if st.button("🚀 Generate Notes", key="doc_button", use_container_width=True):
                        try:
                            # Prepare files for backend processing
                            files = [("files", (doc_file.name, doc_file.getvalue(), doc_file.type)) for doc_file in doc_files]

                            with st.spinner("Generating release notes..."):
                                # Call backend to process files
                                response = handle_api_request(
                                    "POST",
                                    "/api/generate-release-notes",
                                    files=files
                                )

                                if response and response.get("success"):
                                    st.success("✅ Successfully generated release notes")
                                    display_release_notes(response, doc_files)
                                else:
                                    error_msg = response.get("message", "Unknown error") if response else "Failed to get response"
                                    st.error(f"Failed to process files: {error_msg}")
                        except Exception as e:
                            st.error(f"❌ Error processing files: {str(e)}")
                            logger.error(f"Error processing files: {str(e)}")

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
            
            media_files = st.file_uploader(
                "Drop your video here or click to browse",
                type=['mp4', 'mpeg', 'm4v', 'mov', 'avi', 'wmv'],
                accept_multiple_files=True
            )
            
            if media_files:
                st.markdown("---")
                with st.container():
                    for media_file in media_files:
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**Selected file**: {media_file.name}")
                        with col2:
                            size = format_size(media_file.size)
                            if (error := check_file_size(media_file, 'media')) is None:
                                st.markdown(f"**Size**: ✅ {size}")
                        with col3:
                            if error is None:
                                st.markdown("**Status**: Ready to process")
                            else:
                                st.markdown(f"**Status**: ❌ {error}")

                    if st.button("🚀 Generate Notes", key="media_button", use_container_width=True):
                        for media_file in media_files:
                            if (error := check_file_size(media_file, 'media')) is None:
                                try:
                                    start_time = time.time()
                                    progress_bar, status_text, time_remaining = display_processing_status(len(media_files))
                                    
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
                                            
                                            # Create a response object that matches our expected format
                                            notes_response = {
                                                "success": True,
                                                "content": response["release_notes"],
                                                "token_usage": response.get("token_usage", 0)
                                            }
                                            
                                            # Display stats and release notes in a new container
                                            display_release_notes(notes_response, [media_file])
                                            
                                            # Show transcript in expandable section with consistent styling
                                            with st.expander("📝 View Original Transcript", expanded=False):
                                                st.markdown("""
                                                <div class="content-container">
                                                    <div class="release-notes">
                                                """, unsafe_allow_html=True)
                                                st.text_area("Full Transcript", response["transcript"], height=200)
                                                st.markdown("</div></div>", unsafe_allow_html=True)
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
