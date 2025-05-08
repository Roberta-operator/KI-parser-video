# Release Notes Generator

An AI-powered release notes generator built with FastAPI and Streamlit that helps teams create consistent, well-structured release notes from various input formats.

## Key Features

- 🚀 AI-Powered Generation with OpenAI GPT-4
- 📄 Support for PDF, TXT, and JSON inputs
- 🔒 Secure user authentication system
- 📝 Template-based generation for consistency
- 📊 History tracking for all generations
- ⚡ Rate-limited API protection
- 💾 PostgreSQL database backend

## Setup

1. **Environment Setup**
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

2. **Configuration**
- Create `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=your_key_here
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
- Upload a file (PDF/TXT/JSON, max 10MB)
- Click "Generate Release Notes"
- View and save the AI-generated release notes

## Security Features

- Bcrypt password hashing with strong password requirements
- Rate limiting (30 requests/minute)
- File validation and secure processing
- SQL injection protection via SQLAlchemy

## Project Structure

```
fastapi-release-notes-mvp/
├── app/
│   ├── routes/
│   │   ├── generate.py    # Release notes generation endpoints
│   │   ├── upload.py      # File upload handling & validation
│   │   └── users.py       # User registration, login & history endpoints
│   ├── utils/
│   │   └── openai_agent.py # OpenAI integration & template processing
│   ├── auth.py            # Authentication & password security
│   ├── database.py        # PostgreSQL configuration & models
│   ├── main.py           # FastAPI app setup & middleware
│   ├── models.py         # Pydantic data validation models
│   └── streamlit.py      # Frontend UI implementation
├── data/
│   └── template.pdf      # Reference template for release notes
├── .env                  # Environment variables (OpenAI API key)
├── app.log              # Application logging
├── requirements.txt     # Python dependencies
└── README.md           # Project documentation
```

Each file serves a specific purpose:
- `routes/*.py`: API endpoint implementations
  - `generate.py`: Handles release notes generation requests
  - `upload.py`: Manages file uploads with type & size validation
  - `users.py`: User management and history tracking
- `utils/openai_agent.py`: Core AI functionality with template-based generation
- `auth.py`: Secure authentication with bcrypt and password validation
- `database.py`: Database models and connection management
- `main.py`: Application configuration, CORS, and rate limiting
- `models.py`: Request/response data validation
- `streamlit.py`: Interactive web interface
- `template.pdf`: Master template for consistent release notes formatting



