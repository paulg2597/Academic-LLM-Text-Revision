import json
import os

SETTINGS_FILE = "settings.json"
SESSION_FILE = "session.json"
AUTOSAVE_DIR = ".autosave"
AUTOSAVE_FILE = os.path.join(AUTOSAVE_DIR, "revision_autosave.json")

def save_settings(api_key, provider, model, context_mode, goals, custom_instructions, split_provider, split_model, english_dialect="American English"):
    settings = {
        "api_key": api_key,
        "provider": provider,
        "model": model,
        "context_mode": context_mode,
        "goals": goals,
        "custom_instructions": custom_instructions,
        "split_provider": split_provider,
        "split_model": split_model,
        "english_dialect": english_dialect
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_session(session_state_dict):
    keys_to_save = [
        "sentences", "paragraphs", "sentence_mapping", 
        "current_index", "history", "original_file_path", 
        "word_count", "active_paragraphs", "style_guidelines"
    ]
    session_data = {}
    for k in keys_to_save:
        if k in session_state_dict:
            session_data[k] = session_state_dict[k]
            
    with open(SESSION_FILE, "w") as f:
        json.dump(session_data, f)

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    if os.path.exists(AUTOSAVE_FILE):
        os.remove(AUTOSAVE_FILE)
    # Also clean up old pickle file if it exists
    old_pickle_file = os.path.join(AUTOSAVE_DIR, "revision_autosave.pkl")
    if os.path.exists(old_pickle_file):
        os.remove(old_pickle_file)

def auto_save_backup(session_state_dict):
    if not os.path.exists(AUTOSAVE_DIR):
        os.makedirs(AUTOSAVE_DIR)
        
    keys_to_save = [
        "sentences", "paragraphs", "sentence_mapping", 
        "current_index", "history", "original_file_path", 
        "word_count", "active_paragraphs", "style_guidelines"
    ]
    session_data = {}
    for k in keys_to_save:
        if k in session_state_dict:
            session_data[k] = session_state_dict[k]
            
    with open(AUTOSAVE_FILE, "w") as f:
        json.dump(session_data, f)

def load_auto_save_backup():
    # Check for new JSON autosave first
    if os.path.exists(AUTOSAVE_FILE):
        try:
            with open(AUTOSAVE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
            
    # Fallback to old pickle file if it exists (for backward compatibility)
    old_pickle_file = os.path.join(AUTOSAVE_DIR, "revision_autosave.pkl")
    if os.path.exists(old_pickle_file):
        try:
            import pickle
            with open(old_pickle_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
            
    return None
