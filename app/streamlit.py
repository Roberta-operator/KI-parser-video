import streamlit as st
import requests
import logging
import io
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Configure page settings
st.set_page_config(
    page_title="Release Notes Generator",
    page_icon="📝",
    layout="wide"
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

# Main app
st.title('Release Notes Generator')

# Main content
st.header("Generate Release Notes")
uploaded_file = st.file_uploader("Upload a file (PDF/TXT/JSON)", type=['pdf', 'txt', 'json'])

if uploaded_file and st.button("Generate Release Notes"):
    with st.spinner('Generating release notes...'):
        files = {"file": uploaded_file}
        response = handle_api_request('POST', '/generate-release-notes', files=files)
        
        if response:
            if response.get("success"):
                st.markdown("### Generated Release Notes")
                generated_text = response["content"]
                st.write(generated_text)
                
                # Add download buttons
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
                        
                        # Process and add content
                        for line in generated_text.split('\n'):
                            if line.strip():  # Skip empty lines
                                # Check if line is a header
                                if line.startswith('#') or line.startswith('Point'):
                                    style = styles['Heading1']
                                else:
                                    style = normal_style
                                
                                story.append(Paragraph(line, style))
                                story.append(Spacer(1, 6))
                        
                        # Build the PDF
                        doc.build(story)
                        pdf_buffer.seek(0)
                        
                        # Offer download
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
                    # TXT Download button
                    st.download_button(
                        label="Download as TXT",
                        data=generated_text,
                        file_name="release_notes.txt",
                        mime="text/plain",
                        key="txt_download"
                    )
            else:
                st.error(f"Error: {response.get('message', 'Failed to generate release notes')}")
