# Release Notes Generator

An AI-powered release notes generator built with FastAPI and Streamlit that helps teams create consistent, well-structured release notes from various input formats like documents and videos.

## Key Features

- 🚀 AI-Powered Generation with OpenAI GPT-4
- 📄 Support for PDF, TXT, and JSON document inputs
- 🎥 Video transcription and processing with Whisper AI
- 🌐 Multi-language support with automatic detection
- 🔒 Secure user authentication system with bcrypt
- 📝 Template-based generation for consistency
- 📊 History tracking for all generations
- ⚡ Rate-limited API protection (10/minute)
- 💾 PostgreSQL database backend
- 📥 Export to PDF and TXT formats

## Setup

1. **Environment Setup**
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

2. **Configuration**
Create `.env` file with your API key:
```
OPENAI_API_KEY=your_openai_key_here
```

3. **Database Setup**
- Install PostgreSQL
- Update DATABASE_URL in `app/database.py`:
```python
DATABASE_URL = "postgresql://username:password@localhost:5433/dbname"
```

4. **Run the Application**
```bash
# Start the FastAPI backend
uvicorn app.main:app --reload

# Start the Streamlit frontend (in a new terminal)
streamlit run app/streamlit.py
```

## Usage

1. **Access Points**
- Backend API: http://localhost:8000
- Frontend UI: http://localhost:8501

2. **Generate Release Notes**
- Login or create an account
- Upload your file:
  - Documents: PDF, TXT, JSON (max 10MB)
  - Media: MP4, MPEG, M4V, MOV, AVI, WMV (max 100MB)
- Click "Generate Notes"
- View, download as PDF, or save as TXT
- For video files, you can also view the full transcript

3. **Language Support**
Automatic language detection and generation in:
- English (en)
- French (fr)
- German (de)
- Spanish (es)
- Italian (it)
- Portuguese (pt)
- Dutch (nl)
- Polish (pl)

## Security Features

- 🔐 Bcrypt password hashing with strong requirements:
  - Minimum 8 characters
  - Uppercase and lowercase letters
  - Numbers
  - Special characters
- ⚡ Rate limiting (10 requests/minute)
- 📝 File validation and secure processing:
  - Size limits (10MB for documents, 100MB for videos)
  - File type validation
  - Secure file handling with memory buffering
- 🛡️ SQL injection protection via SQLAlchemy
- 🌐 CORS and trusted host middleware

## Project Structure

```
fastapi-release-notes-mvp/
├── app/
│   ├── routes/
│   │   ├── generate.py    # Release notes generation endpoint
│   │   ├── upload.py      # Video upload and processing
│   │   └── users.py       # User auth & history tracking
│   ├── utils/
│   │   ├── openai_agent.py  # OpenAI & template processing
│   │   └── file_processor.py # File handling & validation
│   ├── auth.py            # Authentication & security
│   ├── database.py        # PostgreSQL models & config
│   ├── main.py           # FastAPI & middleware setup
│   ├── models.py         # Data validation models
│   └── streamlit.py      # Frontend interface
├── data/
│   └── template.pdf      # Release notes template
├── temp_videos/         # Temporary video storage
├── .env                 # OpenAI API key
├── app.log             # Application logs
├── requirements.txt    # Python dependencies
└── README.md          # Documentation
```

The application is divided into four main components:

1. **Frontend (Streamlit)**
   - User-friendly interface with drag-and-drop uploads
   - Real-time processing status and progress tracking
   - PDF and TXT export options
   - Video transcript viewing

2. **Backend (FastAPI)**
   - Secure REST API endpoints
   - Rate limiting and error handling
   - Middleware for security and monitoring
   - Background task processing

3. **AI Processing**
   - OpenAI GPT-4 for release notes generation
   - Whisper AI for video transcription
   - Automatic language detection and support
   - Template-based output formatting

4. **Data Storage**
   - PostgreSQL for user data and history
   - Secure file handling with memory buffering
   - Temporary storage for video processing



