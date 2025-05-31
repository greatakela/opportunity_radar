# Opportunity Radar

An AI-powered job search assistant that helps you find and evaluate job opportunities based on your resume and preferences.

## Features

- Automated job search and classification
- AI-powered job scoring based on resume matching
- Company information enrichment
- Job opportunity tracking and management

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/opportunity_radar.git
cd opportunity_radar
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API keys:
```
OPENAI_API_KEY=your_openai_api_key
SERPAPI_API_KEY=your_serp_api_key
```

5. Add your resume:
- Create a `resume.txt` file in the project root
- Format it with sections like SUMMARY, PROJECTS, SKILLS, etc.

6. Add search terms:
- Create a `keywords.csv` file in the project root
- Format it with search query, one per line

## Usage

Run the pipeline to search for and process job opportunities:
```bash
python run_pipeline.py
```

## Project Structure

- `src/agents/` - Core agents for job processing
  - `scoring.py` - Job scoring and resume matching
  - `jobs.py` - Job processing and management
  - `companies.py` - Company information handling
- `src/vector.py` - Vector embeddings and storage
- `data/` - Data storage (created automatically)
- `run_pipeline.py` - Main execution script

## Requirements

- Python 3.8+
- OpenAI API key
- ChromaDB for vector storage

## License

MIT License 