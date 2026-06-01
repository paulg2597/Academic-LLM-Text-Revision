# Generative Text Revision Suite

A powerful, interactive academic writing assistant designed to elevate your research papers through meticulously guided LLM revisions.

**Created by:** [paul-gi.es](https://paul-gi.es) | [GitHub: paulg2597](https://github.com/paulg2597)  
*Vibe coded using Antigravity with Gemini 3.1 Pro (low)*

---

## 🎯 Introduction: Why This Exists

For non-native academics, good academic writing is a critical skill that needs to be actively honed. Simply blasting a whole text into an LLM doesn't help you learn, and your unique authorial style gets completely lost in the process. 

The **Generative Text Revision Suite** is built to solve this. By reviewing and deciding on every revision on a sentence-by-sentence basis, you remain in complete control and actively learn from your mistakes. This deliberate pacing helps you avoid pitfalls like AI hallucinations. Additionally, this tool promotes absolute transparency by auto-generating fully transparent integrity reports of every change, and it reinforces learning by generating a custom summary of your mistakes and tips for future writing.

## ⚙️ Installation

To run this application locally, you will need Python 3.9+ installed on your system.

1. **Download the repository:**
   - **For beginners:** Click the green `<> Code` button at the top of this GitHub page and select **Download ZIP**. Extract the folder to your computer and open it in your terminal/command prompt.
   - **For advanced users:**
     ```bash
     git clone https://github.com/paulg2597/Academic-LLM-Text-Revision.git
     cd llm-text-editor
     ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   streamlit run app.py
   ```
   The application will automatically open in your default web browser at `http://localhost:8501`.

## 🚀 Overview of Functions

The application breaks down the daunting task of revising an entire paper into three manageable steps:

1. **Text Preparation:** Upload your `.docx` file. The app extracts all paragraphs and allows you to easily exclude sections that don't need revision (e.g., References, Appendices, or Title Pages).
2. **Iterative Revision:** The core of the app. It breaks your active paragraphs down into individual sentences. For each sentence, an LLM acts as an expert editor, evaluating it against your defined goals (Grammar, Flow, Conciseness). If issues are found, the LLM provides 3 alternative suggestions and an explanation. You can apply a suggestion, edit it manually, or keep your original text. The app dynamically builds "Active Style Guidelines" as you go to enforce consistency.
3. **Export & Learning:** Once finished, the app generates three files:
   - A fully styled, revised `.docx` file that matches your original document's formatting.
   - An Integrity Report (`.xlsx`) detailing every change you made.
   - A Learning Summary (`.md`), written by an AI "writing coach", summarizing your common mistakes and providing actionable tips for your future writing.

## 📖 User Manual

### Starting a Session
1. **Configure API Settings:** Open the sidebar on the left. Enter your API key for your chosen provider (OpenAI, Anthropic, Mistral, etc.).
2. **Prompt Engineering:** Define your revision goals, choose your preferred English dialect, and add any custom instructions (e.g., "Use a highly formal tone").
3. **Upload Document:** Upload a `.docx` file. If you have a previously saved session, you can upload its Integrity Report (`.xlsx`) alongside the `.docx` to seamlessly resume where you left off!
4. **Prepare Text:** Uncheck any paragraphs you want the LLM to ignore. Use the bulk-uncheck button (⬇️) to quickly deselect entire reference sections.

### The Revision Loop
- **Review and Decide:** For each sentence, review the current text, the possible mistakes identified by the LLM, and decide on an improvement. You can select a suggestion and further customize it in the final edit text box. Once you are satisfied, click **"Apply & Next Sentence"**.
- **Hotkeys are your friend:** Use `1`, `2`, `3`, or `4` to quickly select between keeping your original sentence or choosing an LLM suggestion. Press `Ctrl + Enter` (or `Cmd + Enter`) to apply the change and move to the next sentence.
- **Auto-Save:** The app silently saves your progress locally (`.autosave`) after every single sentence. If you accidentally close the browser, simply restart the app and click "Recover from Crash".
- **Finish Early:** If you're short on time, click "🛑 Finish Early & Export". The app will compile everything you've done so far, leaving the rest of the document in its original state.

---

## ⚠️ Disclaimers & Liability (Disclaimer of Liability)

Please read carefully before using this application:

### 1. Data Protection & Privacy
**Your text is sent to third-party LLM providers.** By using this application and entering an API key, the text of your uploaded documents is transmitted to external servers (e.g., OpenAI, Anthropic, Mistral) for processing. 
- **Do not** upload documents containing highly sensitive, classified, or personally identifiable information (PII) unless you explicitly trust your API provider's data retention policies.
- **Local Execution:** While the Streamlit UI runs locally on your machine, the text processing relies entirely on external cloud APIs (except for if you configure it to use local models).

### 2. Financial Liability & API Costs
**You are entirely responsible for the API costs incurred while using this tool.** 
- **Token Blasts:** Generative AI models consume tokens for both input (context) and output (suggestions). Revising a massive document can quickly become expensive. 
- **Prepaid Limits Highly Recommended:** The developer of this application is **strictly not liable** for any unexpected charges, API token blasts, or financial damages resulting from the use of this software. It is **strongly advised** to set hard billing limits or use prepaid API credits in your provider's dashboard to ensure your safety.

### 3. Academic Integrity
The suggestions provided by the LLM are generated by AI and may occasionally be stylistically awkward, factually incorrect, or "hallucinated." 
- You, the human author, are solely responsible for reviewing and validating every change before publishing or submitting your academic work.
- Always check your institution's guidelines regarding the use of AI tools in academic writing.
