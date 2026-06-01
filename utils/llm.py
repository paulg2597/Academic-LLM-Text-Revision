import json
import time
import litellm
from litellm import model_cost

def get_suggestions(api_key, model, current_sentence, context_text, goals, custom_instructions, style_guidelines, english_dialect="American English"):
    if not api_key:
        raise ValueError("API Key is required.")
        
    goals_list = [k for k, v in goals.items() if v]
    goals_text = "- " + "\n- ".join(goals_list) if goals_list else "- General improvement"
    
    style_guidelines_text = "- " + "\n- ".join(style_guidelines) if style_guidelines else "None currently."
    
    prompt = f"""You are an expert academic editor. Your task is to evaluate the given sentence against the revision goals and provide an explanation and alternative revisions.
    
Your revision goals are:
{goals_text}

Required English Dialect: {english_dialect}

Active Style Guidelines (You must adhere to these, e.g., consistent vocabulary substitutions):
{style_guidelines_text}

Additional Instructions:
{custom_instructions if custom_instructions else 'None.'}
    
Context (Do not edit this, use it only to understand the flow):
{context_text if context_text else 'No preceding context.'}

Sentence to revise:
{current_sentence}

First, determine if the sentence is already perfect given the goals and style guidelines. If it is, set "is_correct" to true, explain why in "mistake_report", and leave "suggestions" empty.
If the sentence has issues or can be improved, set "is_correct" to false, detail the issues in "mistake_report", and provide exactly 3 alternative revisions in "suggestions".
If you notice a recurring stylistic error or make a specific vocabulary substitution that should be applied to the rest of the document, add a concise rule to "new_style_guidelines". Otherwise leave it empty.

Return your response strictly as a JSON object with exactly these four keys: "is_correct" (boolean), "mistake_report" (string), "suggestions" (array of strings), and "new_style_guidelines" (array of strings). Do not include any other text.
Example for correct sentence:
{{
  "is_correct": true,
  "mistake_report": "The sentence is grammatically correct and flows well.",
  "suggestions": [],
  "new_style_guidelines": []
}}
Example for incorrect sentence:
{{
  "is_correct": false,
  "mistake_report": "The sentence uses passive voice and has a spelling error.",
  "suggestions": ["Revision 1.", "Revision 2.", "Revision 3."],
  "new_style_guidelines": ["Always substitute 'x' for 'y'"]
}}
"""
    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        
        # Clean potential markdown wrapping
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:-3].strip()
        elif cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:-3].strip()
            
        result = json.loads(cleaned_content)
        
        if not isinstance(result, dict) or "is_correct" not in result:
             raise ValueError("LLM returned invalid JSON structure")
             
        # Ensure we have at least 3 if not correct, pad if necessary
        if not result["is_correct"]:
            if "suggestions" not in result or not isinstance(result["suggestions"], list):
                result["suggestions"] = []
            while len(result["suggestions"]) < 3:
                result["suggestions"].append(f"Could not generate suggestion {len(result['suggestions'])+1}")
            result["suggestions"] = result["suggestions"][:3]
        else:
            result["suggestions"] = []
            
        if "new_style_guidelines" not in result or not isinstance(result["new_style_guidelines"], list):
            result["new_style_guidelines"] = []
            
        result["usage"] = {
            "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') and hasattr(response.usage, 'prompt_tokens') else 0,
            "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') and hasattr(response.usage, 'completion_tokens') else 0
        }
            
        return result
    except Exception as e:
        return {
            "is_correct": False,
            "mistake_report": f"Error from LLM: {str(e)}. Please check your API key or model.",
            "suggestions": ["", "", ""],
            "new_style_guidelines": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}
        }

def split_sentences_llm(api_key, model, text):
    if not api_key:
        raise ValueError("API Key is required.")
        
    prompt = f"""You are an expert text processing system. Your task is to take the following paragraph and split it into individual sentences. 
Do not alter the text, do not fix grammar, do not omit anything. Just split it where sentences logically end.

Return your response strictly as a JSON array of strings, where each string is a sentence. Do not include any other text.
Example:
["This is sentence one.", "This is sentence two!"]

Paragraph:
{text}
"""
    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        
        cleaned_content = content.strip()
        if cleaned_content.startswith("```json"):
            cleaned_content = cleaned_content[7:-3].strip()
        elif cleaned_content.startswith("```"):
            cleaned_content = cleaned_content[3:-3].strip()
            
        result = json.loads(cleaned_content)
        if not isinstance(result, list):
            raise ValueError("LLM did not return a list")
            
        return [str(s).strip() for s in result if str(s).strip()]
    except Exception as e:
        print(f"Error splitting sentences: {e}")
        # Fallback to regex if LLM fails
        import re
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

def get_mock_suggestions(current_sentence):
    time.sleep(1) # Simulate API delay
    # Alternate between correct and incorrect for testing
    is_correct = len(current_sentence) % 2 == 0
    if is_correct:
         return {
            "is_correct": True,
            "mistake_report": "The sentence is perfect as is because its length is an even number.",
            "suggestions": [],
            "usage": {"prompt_tokens": 45, "completion_tokens": 15}
         }
    else:
        return {
            "is_correct": False,
            "mistake_report": "The sentence is odd. It needs to be evened out.",
            "suggestions": [
                f"Mock Revision 1: {current_sentence}",
                f"Mock Revision 2: {current_sentence}",
                f"Mock Revision 3: {current_sentence}"
            ],
            "usage": {"prompt_tokens": 45, "completion_tokens": 120}
        }

def calculate_cost_estimate(word_count, context_mode, model_name):
    if not word_count or word_count == 0 or not model_name:
        return 0.0
        
    tokens = word_count * 1.33 # approx 1.33 tokens per word
    num_sentences = max(1, word_count / 20) # approx 20 words per sentence
    output_tokens_per_call = 150
    total_output_tokens = num_sentences * output_tokens_per_call
    
    if context_mode == "Full History":
        first_call_tokens = 26
        last_call_tokens = tokens
        total_input_tokens = (num_sentences / 2) * (first_call_tokens + last_call_tokens)
    elif context_mode == "Paragraph":
        total_input_tokens = num_sentences * 260
    else: # Fixed 3-Sentence
        total_input_tokens = num_sentences * 104
        
    cost_in_per_token = 0
    cost_out_per_token = 0
    
    if model_name in model_cost:
        cost_in_per_token = model_cost[model_name].get("input_cost_per_token", 0)
        cost_out_per_token = model_cost[model_name].get("output_cost_per_token", 0)
        
    cost_in = total_input_tokens * cost_in_per_token
    cost_out = total_output_tokens * cost_out_per_token
    
    return cost_in + cost_out

def generate_learning_summary(api_key, model, history_data):
    if not api_key:
        if model == "Mock Test Mode":
            return "Mock Summary: You often write sentences that are too long. Tip: keep them short."
        return "API Key required for learning summary."
        
    # Compile the mistakes
    mistakes_text = ""
    for item in history_data:
        if item.get("Mistake Report") and item.get("Mistake Report") not in ["Skipped", "The sentence is grammatically correct and flows well."]:
            mistakes_text += f"Original: {item.get('Original')}\nMistakes: {item.get('Mistake Report')}\n\n"
            
    if not mistakes_text.strip():
        return "You did not make any significant mistakes! Great job."
        
    prompt = f"""You are an expert writing coach. Based on the following record of mistakes made by the user in their academic document, generate a highly detailed and comprehensive "Common Mistakes and Tips for Future Writing" report.
Do not limit the number of mistakes. Thoroughly analyze all significant grammatical, structural, and stylistic patterns present in the record. For each identified pattern, provide specific examples from the user's text and offer actionable, practical tips to help the young academic improve their writing. Keep the tone encouraging but academically rigorous.

Record of mistakes:
{mistakes_text}
"""
    try:
        response = litellm.completion(
            model=model,
            api_key=api_key,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate learning summary due to an error: {e}"
