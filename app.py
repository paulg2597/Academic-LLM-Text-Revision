import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile
import re
from litellm import model_list, model_cost
from utils.document import extract_paragraphs, split_sentences, create_revised_docx, create_integrity_report
from utils.llm import get_suggestions, get_mock_suggestions, calculate_cost_estimate, generate_learning_summary
from utils.persistence import save_settings, load_settings, save_session, load_session, clear_session, auto_save_backup, load_auto_save_backup

st.set_page_config(page_title="Generative Text Revision Suite", layout="wide", initial_sidebar_state="auto")

# CSS for sleekness
st.markdown("""
<style>
    /* Hide Streamlit default footer */
    footer {display: none;}
    
    /* Sleeker buttons */
    .stButton>button {
        border-radius: 8px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Softer inputs */
    .stTextArea textarea {
        border-radius: 8px;
        border: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# Hotkeys JS snippet
HOTKEYS_JS = """
<script>
const doc = window.parent.document;

// Hide the mock toggle button
const hideBtn = () => {
    const btns = Array.from(doc.querySelectorAll('button'));
    const toggleBtn = btns.find(b => b.innerText.includes('ToggleMockModeBtn'));
    if (toggleBtn) {
        const container = toggleBtn.closest('div[data-testid="stButton"]');
        if (container) container.style.display = 'none';
    }
};
// Run once immediately and observe for changes
hideBtn();
const observer = new MutationObserver(hideBtn);
observer.observe(doc.body, { childList: true, subtree: true });

doc.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'Enter') {
        const btns = Array.from(doc.querySelectorAll('button'));
        const applyBtn = btns.find(b => b.innerText.includes('Apply & Next Sentence'));
        if (applyBtn) applyBtn.click();
    }
    if (['1', '2', '3', '4'].includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey && doc.activeElement.tagName !== 'TEXTAREA' && doc.activeElement.tagName !== 'INPUT') {
        const radios = doc.querySelectorAll('input[type="radio"]');
        const index = parseInt(e.key) - 1;
        if (radios[index]) radios[index].click();
    }
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'n') {
        const btns = Array.from(doc.querySelectorAll('button'));
        const toggleBtn = btns.find(b => b.innerText.includes('ToggleMockModeBtn'));
        if (toggleBtn) toggleBtn.click();
    }
});
</script>
"""
components.html(HOTKEYS_JS, height=0, width=0)

# Load settings
if "settings_loaded" not in st.session_state:
    settings = load_settings()
    st.session_state.api_key = settings.get("api_key", "")
    st.session_state.provider = settings.get("provider", "Mock Test Mode")
    st.session_state.model = settings.get("model", "Mock Test Mode")
    st.session_state.context_mode = settings.get("context_mode", "Paragraph")
    st.session_state.goals = settings.get("goals", {"Grammar & Spelling": True, "Academic Style": True, "Flow": False, "Conciseness": False})
    st.session_state.custom_instructions = settings.get("custom_instructions", "")
    st.session_state.split_provider = settings.get("split_provider", "Mock Test Mode")
    st.session_state.split_model = settings.get("split_model", "Mock Test Mode")
    st.session_state.settings_loaded = True

# Initialize Session State
if "mock_mode_enabled" not in st.session_state:
    st.session_state.mock_mode_enabled = False
if "running_input_tokens" not in st.session_state:
    st.session_state.running_input_tokens = 0
    st.session_state.running_output_tokens = 0
    st.session_state.running_cost = 0.0
if "sentences" not in st.session_state:
    st.session_state.sentences = []
    st.session_state.paragraphs = []
    st.session_state.active_paragraphs = []
    st.session_state.sentence_mapping = []
    st.session_state.current_index = 0
    st.session_state.history = []
    st.session_state.current_evaluation = None
    st.session_state.original_file_path = ""
    st.session_state.word_count = 0
    st.session_state.style_guidelines = []
    st.session_state.step = 0 # 0: upload/resume, 1: prepare, 2: edit

def get_context(mode, current_idx):
    if current_idx == 0:
        return ""
    finalized = [item["Final"] for item in st.session_state.history]
    if mode == "Full History":
        return " ".join(finalized)
    elif mode == "Fixed 3-Sentence":
        return " ".join(finalized[-3:])
    elif mode == "Paragraph":
        curr_p_idx = st.session_state.sentence_mapping[current_idx]
        context_sentences = []
        for i, item in enumerate(st.session_state.history):
            if st.session_state.sentence_mapping[i] >= curr_p_idx - 1:
                context_sentences.append(item["Final"])
        return " ".join(context_sentences)
    return ""

import pandas as pd

def load_document(file, report_file=None):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name
        
    paras = extract_paragraphs(tmp_path)
    st.session_state.paragraphs = paras
    st.session_state.active_paragraphs = [True] * len(paras)
    st.session_state.original_file_path = tmp_path
    st.session_state.step = 1 # Go to preparation
    st.session_state.sentences = []
    st.session_state.current_index = 0
    st.session_state.history = []
    st.session_state.current_evaluation = None
    st.session_state.style_guidelines = []
    st.session_state.resume_idx = 0
    
    if "loaded_sentences" in st.session_state:
        del st.session_state["loaded_sentences"]
    if "loaded_mapping" in st.session_state:
        del st.session_state["loaded_mapping"]
    
    if report_file is not None:
        try:
            df = pd.read_excel(report_file)
            history_data = df.to_dict('records')
            
            if "Style Notes" in df.columns:
                all_notes = df["Style Notes"].dropna().astype(str).tolist()
                for notes_block in all_notes:
                    if notes_block and notes_block != "Skipped":
                        for note in notes_block.split("\n"):
                            if note and note not in st.session_state.style_guidelines:
                                st.session_state.style_guidelines.append(note)
                                
            resume_idx = 0
            all_sents = []
            mapping = []
            
            for i, row in enumerate(history_data):
                orig = row.get("Original", "")
                action_val = row.get("Action", "")
                if pd.isna(orig) and pd.isna(action_val):
                    continue
                    
                orig_str = "" if pd.isna(orig) else str(orig)
                all_sents.append(orig_str)
                
                # Check for perfect mapping in new reports
                if "Paragraph Index" in row and pd.notna(row["Paragraph Index"]):
                    mapping.append(int(row["Paragraph Index"]))
                
                action = str(row.get("Action", ""))
                # Stop restoring when we hit the skipped/finished early mark
                if "Finished Early" in action or "Skipped" in action:
                    continue # Keep extracting sentences, but stop adding to history
                    
                if resume_idx == i: # Only append if we haven't hit the stop mark yet
                    # Convert Suggestions back to a list if it was a string
                    if "Suggestions" in row and isinstance(row["Suggestions"], str):
                        row["Suggestions"] = [s.strip() for s in row["Suggestions"].split('\n') if s.strip()]
                    st.session_state.history.append(row)
                    resume_idx += 1
                    
            st.session_state.resume_idx = resume_idx
            
            # Reconstruct mapping for old reports if missing
            if len(mapping) < len(all_sents):
                mapping = []
                p_idx = 0
                paras = st.session_state.paragraphs
                for s in all_sents:
                    s_clean = s.strip()
                    found = False
                    for p in range(p_idx, len(paras)):
                        if s_clean in paras[p]:
                            mapping.append(p)
                            p_idx = p
                            found = True
                            break
                    if not found:
                        mapping.append(p_idx)
            
            st.session_state.loaded_sentences = all_sents
            st.session_state.loaded_mapping = mapping
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            st.error(f"Error loading report: {e}")
            st.session_state.step = 0

def start_revision():
    if "loaded_sentences" in st.session_state:
        sents = st.session_state.loaded_sentences
        mapping = st.session_state.loaded_mapping
    else:
        with st.spinner("Splitting text into sentences..."):
            split_litellm_model = get_litellm_model_string(st.session_state.split_provider, st.session_state.split_model) if st.session_state.split_model != "Mock Test Mode" else "Mock Test Mode"
            sents, mapping = split_sentences(st.session_state.paragraphs, st.session_state.active_paragraphs, st.session_state.api_key, split_litellm_model)
    st.session_state.sentences = sents
    st.session_state.sentence_mapping = mapping
    st.session_state.word_count = sum(len(s.split()) for s in sents)
    
    if st.session_state.get("resume_idx", 0) > 0:
        st.session_state.current_index = st.session_state.resume_idx
        
    st.session_state.step = 2

def finish_early():
    # Treat remaining sentences as "Kept Original"
    while st.session_state.current_index < len(st.session_state.sentences):
        idx = st.session_state.current_index
        st.session_state.history.append({
            "Sentence Index": idx + 1,
            "Paragraph Index": st.session_state.sentence_mapping[idx],
            "Original": st.session_state.sentences[idx],
            "Suggestions": [],
            "Mistake Report": "Skipped",
            "Final": st.session_state.sentences[idx],
            "Action": "Kept Original (Finished Early)",
            "Style Notes": "Skipped"
        })
        st.session_state.current_index += 1
    st.session_state.current_evaluation = None
    st.session_state.step = 3 # Export step

def get_model_sort_key(model_name):
    name_lower = model_name.lower()
    
    # 1. Extract major/minor version (e.g., 3.5 from claude-3-5, 1.5 from gemini-1.5)
    version_score = 0.0
    if "o3" in name_lower: version_score = 10.0
    elif "o1" in name_lower: version_score = 9.0
    elif "gpt-4o" in name_lower: version_score = 4.5
    else:
        # Match first occurrence of digits acting as version (e.g., 3.1, 2.5, 4, 3-5)
        v_match = re.search(r'(?:gemini|claude|gpt|mistral|mixtral)[^\d]*(\d+)(?:[.-](\d+))?', name_lower)
        if v_match:
            major = float(v_match.group(1))
            minor = float(v_match.group(2)) if v_match.group(2) else 0.0
            version_score = major + (minor / 10.0)
            
    # 2. Extract Date if present
    date_val = 0
    date_match = re.search(r'(202\d[-]?\d{2}[-]?\d{2})', model_name)
    if date_match:
        date_str = date_match.group(1).replace("-", "")
        date_val = int(date_str)
    else:
        # Try MMDD at the end (OpenAI style)
        mmdd_match = re.search(r'-(\d{4})$', model_name)
        if mmdd_match:
            date_val = int(mmdd_match.group(1))
            
    # Combine scores. Version is heavily weighted over date.
    final_score = (version_score * 100000000) + date_val
    cost = model_cost.get(model_name, {}).get("input_cost_per_token", 0)
    
    # Sort descending by version/date score, then descending by cost (larger models first), then alphabetically
    return (-final_score, -cost, model_name)

def get_litellm_model_string(provider, model):
    if provider == "Anthropic" and not model.startswith("anthropic/"): return f"anthropic/{model}"
    if provider == "Google" and not model.startswith("gemini/"): return f"gemini/{model}"
    if provider == "Mistral" and not model.startswith("mistral/"): return f"mistral/{model}"
    if provider == "OpenAI" and not model.startswith("openai/"): return f"openai/{model}"
    return model

st.title("📝 Generative Text Revision Suite")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    
    # Hidden button for mock mode toggle
    if st.button("ToggleMockModeBtn", key="toggle_mock_btn"):
        st.session_state.mock_mode_enabled = not st.session_state.mock_mode_enabled
        st.rerun()
    
    PROVIDERS = ["OpenAI", "Anthropic", "Google", "Mistral", "Custom"]
    if st.session_state.mock_mode_enabled:
        PROVIDERS.insert(0, "Mock Test Mode")
        
    new_provider = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(st.session_state.provider) if st.session_state.provider in PROVIDERS else 0)
    
    # Filter models based on provider
    if new_provider == "Mock Test Mode":
        filtered_models = ["Mock Test Mode"]
    elif new_provider == "Custom":
        filtered_models = []
    else:
        prefix_map = {"OpenAI": ["gpt-", "o1-"], "Anthropic": ["claude-"], "Google": ["gemini-"], "Mistral": ["mistral", "open-mistral", "open-mixtral", "codestral", "ministral", "pixtral"]}
        prefixes = prefix_map.get(new_provider, [])
        filtered_models = []
        for m in model_cost.keys():
            # Skip AWS Bedrock specific strings and explicit alternate provider prefixes
            if m.startswith("anthropic.") or m.startswith("mistral.") or m.startswith("meta.") or m.startswith("amazon.") or m.startswith("cohere."):
                continue
            if m.startswith("bedrock/") or m.startswith("azure/") or m.startswith("vertex_ai/"):
                continue
            if ":" in m:
                continue
                
            if any(m.startswith(p) or m.startswith(f"{new_provider.lower()}/{p}") for p in prefixes):
                filtered_models.append(m)
                
        if filtered_models:
            # Remove duplicates if any
            filtered_models = list(set(filtered_models))
            filtered_models.sort(key=get_model_sort_key)
        else:
            filtered_models = ["(No models found in litellm dict)"]
            
    if new_provider == "Custom":
        new_model = st.text_input("Custom Model Name", value=st.session_state.model)
    else:
        # Keep old model if it exists in filtered list, else select first
        m_index = filtered_models.index(st.session_state.model) if st.session_state.model in filtered_models else 0
        new_model = st.selectbox("Model", filtered_models, index=m_index)
        
        new_context = st.selectbox("Context Window", ["Paragraph", "Fixed 3-Sentence", "Full History"], index=["Paragraph", "Fixed 3-Sentence", "Full History"].index(st.session_state.context_mode))
        
        # Display Token Cost
        if new_model and new_model != "Mock Test Mode" and new_model != "(No models found in litellm dict)":
            if new_model in model_cost:
                in_c = model_cost[new_model].get("input_cost_per_token", 0) * 1_000_000
                out_c = model_cost[new_model].get("output_cost_per_token", 0) * 1_000_000
                st.caption(f"Cost: USD {in_c:.2f} / 1M In | USD {out_c:.2f} / 1M Out")
                
                # Estimated cost per 1000 words
                est_1k = calculate_cost_estimate(1000, new_context, new_model)
                st.caption(f"Est. per 1000 words: ${est_1k:.4f}")
            else:
                st.caption("Pricing not available for this model.")
                
        new_api_key = st.session_state.api_key
        if new_provider != "Mock Test Mode":
            new_api_key = st.text_input("API Key", type="password", value=st.session_state.api_key)
            
    with st.expander("Sentence Splitting Model", expanded=False):
        new_split_provider = st.selectbox("Split Provider", PROVIDERS, index=PROVIDERS.index(st.session_state.split_provider) if st.session_state.split_provider in PROVIDERS else 0)
        
        if new_split_provider == "Mock Test Mode":
            split_filtered_models = ["Mock Test Mode"]
        elif new_split_provider == "Custom":
            split_filtered_models = []
        else:
            split_prefixes = prefix_map.get(new_split_provider, [])
            split_filtered_models = []
            for m in model_cost.keys():
                if m.startswith("anthropic.") or m.startswith("mistral.") or m.startswith("meta.") or m.startswith("amazon.") or m.startswith("cohere."):
                    continue
                if m.startswith("bedrock/") or m.startswith("azure/") or m.startswith("vertex_ai/"):
                    continue
                if ":" in m:
                    continue
                if any(m.startswith(p) or m.startswith(f"{new_split_provider.lower()}/{p}") for p in split_prefixes):
                    split_filtered_models.append(m)
            if split_filtered_models:
                split_filtered_models = list(set(split_filtered_models))
                split_filtered_models.sort(key=get_model_sort_key)
            else:
                split_filtered_models = ["(No models found in litellm dict)"]
                
        if new_split_provider == "Custom":
            new_split_model = st.text_input("Custom Split Model Name", value=st.session_state.split_model)
        else:
            sm_index = split_filtered_models.index(st.session_state.split_model) if st.session_state.split_model in split_filtered_models else 0
            new_split_model = st.selectbox("Split Model", split_filtered_models, index=sm_index)
    
    with st.expander("Prompt Engineering", expanded=False):
        st.write("Revision Goals:")
        new_goals = {}
        for goal, val in st.session_state.goals.items():
            new_goals[goal] = st.checkbox(goal, value=val)
            
        new_english_dialect = st.selectbox(
            "English Dialect", 
            ["American English", "British English"], 
            index=["American English", "British English"].index(st.session_state.get("english_dialect", "American English"))
        )
        
        new_custom_instructions = st.text_area("Custom Instructions", value=st.session_state.custom_instructions, placeholder="E.g., Use a formal tone")

    # Save settings if changed
    if (new_provider != st.session_state.provider or new_model != st.session_state.model or 
        new_api_key != st.session_state.api_key or new_context != st.session_state.context_mode or 
        new_goals != st.session_state.goals or new_custom_instructions != st.session_state.custom_instructions or
        new_split_provider != st.session_state.split_provider or new_split_model != st.session_state.split_model or
        new_english_dialect != st.session_state.get("english_dialect")):
        st.session_state.provider = new_provider
        st.session_state.model = new_model
        st.session_state.api_key = new_api_key
        st.session_state.context_mode = new_context
        st.session_state.goals = new_goals
        st.session_state.custom_instructions = new_custom_instructions
        st.session_state.split_provider = new_split_provider
        st.session_state.split_model = new_split_model
        st.session_state.english_dialect = new_english_dialect
        save_settings(new_api_key, new_provider, new_model, new_context, new_goals, new_custom_instructions, new_split_provider, new_split_model, new_english_dialect)
    
    st.markdown("---")
    
    if st.session_state.step == 2:
        if st.button("💾 Save & Quit", use_container_width=True):
            state_dict = {k: v for k, v in st.session_state.items()}
            save_session(state_dict)
            st.success("Session saved! You can safely close the app.")
            
    if st.session_state.step == 0:
        st.warning("⚠️ **Data Protection:** By uploading a document, its text will be sent to the selected LLM API provider.")
        uploaded_file = st.file_uploader("Upload Original Word Document (.docx)", type=["docx"])
        uploaded_report = st.file_uploader("Upload Integrity Report (.xlsx) to Resume (Optional)", type=["xlsx"])
        if uploaded_file is not None:
            if st.button("Load Document"):
                load_document(uploaded_file, uploaded_report)
                st.rerun()
                
    if st.session_state.word_count > 0 and st.session_state.step == 2:
        st.markdown("### Cost Estimate")
        st.write(f"**Document Length:** ~{st.session_state.word_count} words")
        cost = calculate_cost_estimate(st.session_state.word_count, st.session_state.context_mode, st.session_state.model)
        st.info(f"**Estimated API Cost:** ${cost:.3f}")
        
    if st.session_state.step > 0:
        if st.button("Start Over", use_container_width=True):
            st.session_state.step = 0
            st.session_state.sentences = []
            st.session_state.current_evaluation = None
            st.session_state.running_input_tokens = 0
            st.session_state.running_output_tokens = 0
            st.session_state.running_cost = 0.0
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #888;'><small>Created by <a href='https://paul-gi.es' target='_blank'>paul-gi.es</a> | <a href='https://github.com/paulg2597' target='_blank'>GitHub</a></small></div>", unsafe_allow_html=True)

# --- MAIN UI ---
if st.session_state.step == 0:
    st.info("👈 Please configure settings and upload a document in the sidebar to begin.")
    
    # Check for saved session
    saved = load_session()
    if saved:
        st.markdown("---")
        st.write("You have a saved session.")
        if st.button("Resume Previous Session"):
            for k, v in saved.items():
                st.session_state[k] = v
            st.session_state.step = 2
            st.rerun()

    # Check for auto-saved session
    autosaved = load_auto_save_backup()
    if autosaved:
        st.markdown("---")
        st.error("🚨 It looks like the app previously crashed or was closed abruptly. You can recover from an auto-save.")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("Recover from Crash (Auto-Save)", type="primary", use_container_width=True):
                for k, v in autosaved.items():
                    st.session_state[k] = v
                st.session_state.step = 2
                st.rerun()
        with col_r2:
            if st.button("Discard Auto-Save", use_container_width=True):
                from utils.persistence import AUTOSAVE_FILE
                import os
                if os.path.exists(AUTOSAVE_FILE):
                    os.remove(AUTOSAVE_FILE)
                st.rerun()

elif st.session_state.step == 1:
    st.header("Step 1: Text Preparation")
    st.write("Uncheck any paragraphs you want the LLM to skip (e.g., references, tables). They will remain unchanged in the final document.")
    
    def uncheck_below(start_idx):
        for j in range(start_idx, len(st.session_state.paragraphs)):
            st.session_state.active_paragraphs[j] = False
            if f"p_{j}" in st.session_state:
                st.session_state[f"p_{j}"] = False

    with st.container(height=500):
        for i, p in enumerate(st.session_state.paragraphs):
            if p.strip():
                col1, col2 = st.columns([11, 1])
                with col1:
                    st.session_state.active_paragraphs[i] = st.checkbox(p, value=st.session_state.active_paragraphs[i], key=f"p_{i}")
                with col2:
                    st.button("⬇️", key=f"uncheck_below_{i}", help="Uncheck this and all following paragraphs", on_click=uncheck_below, args=(i,))
                
    if st.button("Confirm & Start Revision", type="primary"):
        start_revision()
        st.rerun()

elif st.session_state.step == 2:
    if not st.session_state.get("sidebar_collapsed"):
        st.session_state.sidebar_collapsed = True
        components.html("""
            <script>
                const doc = window.parent.document;
                const sidebarToggle = doc.querySelector('[data-testid="collapsedControl"]');
                if (sidebarToggle && sidebarToggle.getAttribute('aria-expanded') === 'true') {
                    sidebarToggle.click();
                }
            </script>
        """, height=0, width=0)
        
    total_sentences = len(st.session_state.sentences)
    current_idx = st.session_state.current_index
    
    if total_sentences == 0:
        st.warning("No sentences found to revise based on your selection.")
    elif current_idx < total_sentences:
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("### Revision Editor")
        with col2:
            if st.button("🛑 Finish Early & Export", use_container_width=True):
                finish_early()
                st.rerun()
                
        st.markdown("---")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            current_sentence = st.session_state.sentences[current_idx]
            
            if current_idx > 0 and len(st.session_state.history) > 0:
                st.markdown(f'<small style="color: #888; font-style: italic;">Prior Sentence: {st.session_state.history[-1]["Final"]}</small>', unsafe_allow_html=True)
                
            st.markdown("### Current Sentence")
            st.write(f"> {current_sentence}")
            
            if current_idx < total_sentences - 1:
                st.markdown(f'<small style="color: #888; font-style: italic;">Next Sentence: {st.session_state.sentences[current_idx + 1]}</small>', unsafe_allow_html=True)
            
            if not st.session_state.current_evaluation:
                with st.spinner("Evaluating sentence..."):
                    context = get_context(st.session_state.context_mode, current_idx)
                    if st.session_state.model == "Mock Test Mode":
                        eval_result = get_mock_suggestions(current_sentence)
                    else:
                        litellm_model = get_litellm_model_string(st.session_state.provider, st.session_state.model)
                        eval_result = get_suggestions(
                            st.session_state.api_key, 
                            litellm_model, 
                            current_sentence, 
                            context, 
                            st.session_state.goals, 
                            st.session_state.custom_instructions, 
                            st.session_state.style_guidelines,
                            st.session_state.get("english_dialect", "American English")
                        )
                    st.session_state.current_evaluation = eval_result
                    st.rerun()
                    
            eval_result = st.session_state.current_evaluation
            is_correct = eval_result.get("is_correct", False)
            report = eval_result.get("mistake_report", "")
            suggestions = eval_result.get("suggestions", [])
            
            if is_correct:
                st.success(f"**Sentence Perfect!**\n\n{report}")
                selected_option = "Keep Original"
                final_text = st.text_area("Final Edit:", value=current_sentence, height=100)
            else:
                st.warning(f"**Mistake Report:**\n\n{report}")
                st.markdown("### Revision Options")
                options = ["Keep Original"] + suggestions
                selected_option = st.radio("Select an option to start with:", options)
                st.markdown("### Final Edit")
                final_text = st.text_area("You can make final tweaks here before applying:", value=selected_option if selected_option != "Keep Original" else current_sentence, height=150)
            
        with c2:
            st.progress(current_idx / total_sentences, text=f"Sentence {current_idx + 1} of {total_sentences}")
            st.markdown("### Running Cost")
            st.caption(f"In: {st.session_state.running_input_tokens} | Out: {st.session_state.running_output_tokens}")
            st.info(f"**Total: ${st.session_state.running_cost:.4f}**")
            
            with st.expander("Active Style Guidelines", expanded=True):
                with st.container(height=150):
                    if not st.session_state.style_guidelines:
                        st.write("No guidelines yet.")
                    else:
                        for g in st.session_state.style_guidelines:
                            st.write(f"- {g}")
        
        if st.button("Apply & Next Sentence", type="primary"):
            action = "Kept Original"
            if final_text != current_sentence:
                if final_text == selected_option:
                    if selected_option in suggestions:
                        action = f"Used Suggestion {suggestions.index(final_text) + 1}"
                else:
                    if selected_option == "Keep Original":
                        action = "Edited (Base: Original)"
                    elif selected_option in suggestions:
                        action = f"Edited (Base: Suggestion {suggestions.index(selected_option) + 1})"
                    else:
                        action = "Manual Edit"
                        
            # Update running costs
            if st.session_state.current_evaluation and "usage" in st.session_state.current_evaluation:
                usage = st.session_state.current_evaluation["usage"]
                in_t = usage.get("prompt_tokens", 0)
                out_t = usage.get("completion_tokens", 0)
                st.session_state.running_input_tokens += in_t
                st.session_state.running_output_tokens += out_t
                
                if st.session_state.model != "Mock Test Mode" and st.session_state.model in model_cost:
                    in_c = model_cost[st.session_state.model].get("input_cost_per_token", 0)
                    out_c = model_cost[st.session_state.model].get("output_cost_per_token", 0)
                    st.session_state.running_cost += (in_t * in_c) + (out_t * out_c)
                    
            new_guidelines = []
            if st.session_state.current_evaluation:
                new_guidelines = st.session_state.current_evaluation.get("new_style_guidelines", [])
                for g in new_guidelines:
                    if g not in st.session_state.style_guidelines:
                        st.session_state.style_guidelines.append(g)
            
            st.session_state.history.append({
                "Sentence Index": current_idx + 1,
                "Paragraph Index": st.session_state.sentence_mapping[current_idx],
                "Original": current_sentence,
                "Suggestions": suggestions,
                "Mistake Report": report,
                "Final": final_text,
                "Action": action,
                "Style Notes": "\n".join(new_guidelines) if new_guidelines else ""
            })
            
            st.session_state.current_index += 1
            st.session_state.current_evaluation = None
            
            # Auto transition to export if we reached the end
            if st.session_state.current_index >= total_sentences:
                st.session_state.step = 3
                
            # Perform auto-save backup
            auto_save_backup({k: v for k, v in st.session_state.items()})
            
            st.rerun()
            
elif st.session_state.step == 3:
    st.success("🎉 You have finished reviewing your document!")
    clear_session()
    
    st.markdown("### Export Files")
    with st.spinner("Generating final documents..."):
        revised_docx_path = os.path.join(tempfile.gettempdir(), "revised_document.docx")
        report_xlsx_path = os.path.join(tempfile.gettempdir(), "integrity_report.xlsx")
        learning_md_path = os.path.join(tempfile.gettempdir(), "learning_summary.md")
        
        finalized_sentences = [item["Final"] for item in st.session_state.history]
        
        create_revised_docx(
            st.session_state.original_file_path, 
            st.session_state.paragraphs, 
            st.session_state.sentences, 
            st.session_state.sentence_mapping, 
            finalized_sentences, 
            st.session_state.active_paragraphs,
            revised_docx_path
        )
        create_integrity_report(st.session_state.history, report_xlsx_path)
        
        # Generate learning summary if not yet generated
        if "learning_summary_text" not in st.session_state:
            st.session_state.learning_summary_text = generate_learning_summary(
                st.session_state.api_key, 
                st.session_state.model, 
                st.session_state.history
            )
        
        with open(learning_md_path, "w", encoding="utf-8") as f:
            f.write("# Common Mistakes and Tips for Future Writing\n\n")
            f.write(st.session_state.learning_summary_text)
        
    col1, col2, col3 = st.columns(3)
    with col1:
        with open(revised_docx_path, "rb") as f:
            st.download_button("📄 Download Revised .docx", data=f, file_name="revised_document.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    with col2:
        with open(report_xlsx_path, "rb") as f:
            st.download_button("📊 Download Integrity Report (.xlsx)", data=f, file_name="integrity_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col3:
        with open(learning_md_path, "rb") as f:
            st.download_button("🎓 Download Learning Summary (.md)", data=f, file_name="learning_summary.md", mime="text/markdown")
