# Assignment Similarity Detection WebApp

This Streamlit application allows students to submit assignments and provides a combined Teacher/Admin dashboard (accessed via the **Moderator** button and a shared pass key).

**Navigation:** Use the top bar buttons to switch between Student or Moderator roles. The old home-page "Enter as …" buttons have been removed.

Teachers can create assignments and optionally upload a question paper, while administrators (moderators) can lock/unlock assignments, trigger analyses, and review results—all from the same interface. OCR and NLP are used to detect similarity between submissions.

## Setup

1. **Install dependencies** (run in project root `WebApp`):

```bash
pip install -r requirements.txt
```

2. **Install Python packages** (listed in `requirements.txt`). The app no longer requires Poppler or `pdf2image` since OCR is performed directly on the uploaded PDF.
3. **Configure secrets**:
   - Create `WebApp/.streamlit/secrets.toml` with MongoDB URI and SMTP credentials (already pre-filled). Ensure the SMTP password is an App Password for Gmail.

4. **Run**:

```bash
streamlit run app.py
```

## Email behaviour

When a moderator analyzes an assignment, the system:

- Uses the text already extracted from each PDF at upload time (OCR.space handles up to 3‑page PDFs directly).
- Runs `nlp_module` cleaning and the similarity engine over the stored text for every roll number.
- Aggregates results per student roll number and computes the similarity matrix.
- Stores the summary in MongoDB and sends an email to the teacher with the matrix and flagged pairs.

## Notes

- Only one PDF is accepted per submission.
- Roll numbers must be exactly 10 characters.
- Uploaded PDFs and question papers are preserved in MongoDB via GridFS; local copies are only temporary and may be removed. Question papers are always served from GridFS so downloads continue to work even if the local file is gone.

Enjoy!
