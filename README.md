# ATS Resume Scorer

A web app that scores how well a resume matches a job description and returns actionable feedback. Built with FastAPI + Streamlit, using spaCy and Sentence Transformers for NLP and the Groq API for LLM-generated suggestions.

## What it does

```mermaid
flowchart TD

A([1. Upload Resume & JD])
--> B[2. Extract Raw Text\npdfplumber / Fallback]

B --> C[Validation]

C --> D{File Corrupted\nor Too Large?}

D -->|Yes| E[Custom Exception\nHTTP 400 / 422]

D -->|No| F[3. LLM Parsing\nGroq]

F --> G[Extract Structured JSON\nContact\nSkills\nExperience]

G --> H[4. AI & NLP Processing]

H --> I[spaCy\nDetect Address\nPrivacy]

H --> J[BERT Embeddings\nVectorize Text]

I --> K[5. Validation & Matching]
J --> K

K --> L[Skill Validation\nFast Path\nSemantic Path]

K --> M[Fuzzy Keyphrase\nJD Semantic Match]

L --> N[6. Scoring Engine]
M --> N

N --> O[Weight Config Matrix\nFormat\nContent\nSkills\nCompetencies]

O --> P[7. Feedback Generation]

P --> Q[Prioritize Issues\nCritical\nMedium\nLow]

Q --> R([Finish Pipeline])

R -->|Async Save| S[(SAVE TO DB)]

R -->|Response| T[9. Format Output]

T --> U[Return JSON\nfor React]

T --> V[Report Generator\nWeasyPrint]

V --> W[Return PDF Bytes]

```

1. Upload a resume (PDF / DOC / DOCX) and paste a job description.
2. The backend parses the resume, extracts skills and experience, and compares them to the JD using semantic similarity.
3. You get an ATS score, a breakdown by category (formatting, keywords, content, skill validation, ATS compatibility), and LLM-written suggestions for what to improve.
4. Past analyses are saved to your account so you can revisit them.

--- 

    
```mermaid
%%{init:{
  "theme":"base",
  "themeVariables":{
    "primaryColor":"#E3F2FD",
    "primaryBorderColor":"#1565C0",
    "primaryTextColor":"#111111",
    "secondaryColor":"#E8F5E9",
    "secondaryBorderColor":"#2E7D32",
    "tertiaryColor":"#FFF8E1",
    "lineColor":"#333333",
    "textColor":"#111111",
    "actorTextColor":"#111111",
    "actorBorder":"#1565C0",
    "actorBkg":"#FFFFFF",
    "signalColor":"#111111",
    "signalTextColor":"#111111",
    "noteTextColor":"#111111",
    "noteBorderColor":"#333333",
    "noteBkgColor":"#FFF9C4",
    "fontSize":"18px"
  }
}}%%

sequenceDiagram
autonumber

actor User
participant UI as Streamlit UI
participant Auth as Supabase Auth
participant API as FastAPI Backend

rect rgb(230,245,255)
Note over User,Auth: 🔑 Authentication (One Time)

User->>UI: Email + Password
activate UI

UI->>Auth: sign_in_with_password()
activate Auth

Auth-->>UI: JWT Access Token
deactivate Auth

Note right of UI: Store JWT in<br/>st.session_state

deactivate UI
end

rect rgb(235,255,235)
Note over User,API: 🚀 Every API Request

User->>UI: Click "Analyze Resume"

activate UI
UI->>API: POST /analyze-resume<br/>Authorization: Bearer JWT

activate API
API->>Auth: Fetch JWKS
activate Auth

Auth-->>API: Public Keys
deactivate Auth

Note right of API: Verify JWT<br/>Extract user_id

API-->>UI: 200 OK + Analysis
deactivate API

UI-->>User: Display Results
deactivate UI
end
```

## Tech stack

- **Frontend:** Streamlit
- **Backend:** FastAPI (Python)
- **NLP:** spaCy (`en_core_web_md`), Sentence Transformers (`all-MiniLM-L6-v2`)
- **LLM:** Groq API (Llama 3)
- **Auth + Database:** Supabase (email/password and Google OAuth)
- **PDF report export:** WeasyPrint + Jinja2

## Project structure

```
ATS_SCORER/
├── backend/              FastAPI app, NLP services, API routes
├── frontend/             Streamlit app, views, components
├── jupyter notebooks/    Research and dataset prep (not used at runtime)
├── ml model/             Exported ML artifacts
├── requirements.txt      Combined backend + frontend dependencies
└── .env.example          Template for environment variables
```

```mermaid
flowchart TD

    A([👤 User Interaction])
    B["🔄 Streamlit reruns<br/>entire script"]
    C["❌ Local Variables<br/>count = 0<br/>Reset every rerun"]
    D["✅ st.session_state<br/>token<br/>Persists across reruns"]
    E["✨ UI Re-renders"]
    F([⏸ Wait for next interaction])

    A --> B
    B --> C
    B --> D
    C --> E
    D --> E
    E --> F
    F -->|Next click / input| A

    style A fill:#E3F2FD,stroke:#1565C0,color:#000,stroke-width:2px
    style B fill:#FFF3E0,stroke:#EF6C00,color:#000,stroke-width:2px
    style C fill:#FFEBEE,stroke:#C62828,color:#000,stroke-width:2px
    style D fill:#E8F5E9,stroke:#2E7D32,color:#000,stroke-width:2px
    style E fill:#F3E5F5,stroke:#6A1B9A,color:#000,stroke-width:2px
    style F fill:#E3F2FD,stroke:#1565C0,color:#000,stroke-width:2px
```

```mermaid
flowchart LR

    ATS(("🎯 ATS Score<br/>out of 100"))

    subgraph SCORE[" "]
        direction TB

        F["📄 Formatting<br/><b>20 pts</b><br/>sections<br/>structure<br/>readability"]

        K["🔑 Keywords<br/><b>25 pts</b><br/>industry terms<br/>tech skills present"]

        C["📝 Content<br/><b>25 pts</b><br/>action verbs<br/>quantified impact"]

        S["✅ Skill Validation<br/><b>15 pts</b><br/>claimed skills<br/>demonstrated in projects"]

        A["🤖 ATS Compatibility<br/><b>15 pts</b><br/>parseable by<br/>automated systems"]
    end

    ATS --> F
    ATS --> K
    ATS --> C
    ATS --> S
    ATS --> A

    %% ---------- Styles ----------
    style ATS fill:#F9C74F,stroke:#F8961E,stroke-width:3px,color:#000

    style F fill:#DCEEFF,stroke:#4A90E2,stroke-width:2px,color:#000
    style K fill:#DCEEFF,stroke:#4A90E2,stroke-width:2px,color:#000
    style C fill:#DCEEFF,stroke:#4A90E2,stroke-width:2px,color:#000
    style S fill:#DCEEFF,stroke:#4A90E2,stroke-width:2px,color:#000
    style A fill:#DCEEFF,stroke:#4A90E2,stroke-width:2px,color:#000

    style SCORE fill:transparent,stroke:transparent
```
