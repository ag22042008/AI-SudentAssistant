import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables from .env
load_dotenv()

# Initialize Gemini LLM
# If GEMINI_API_KEY is not set globally, it will be read from .env
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", 
    temperature=0.2
)

def extract_topic(question: str, subject: str) -> str:
    """
    Extracts a 2-5 word specific topic label for the question.
    """
    system_prompt = f"You are a helpful assistant. The subject is {subject}. Please read the following question and respond ONLY with a short, specific topic label (2-5 words) that classifies it (e.g. 'Quadratic Equations', 'Newton's Second Law'). Do not include trailing punctuation or conversation."
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Question: {question}")
    ]
    try:
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
        elif not isinstance(content, str):
            content = str(content)
        return content.strip().strip('"').strip("'")
    except Exception as e:
        return "General Request"

def get_next_hint(question: str, subject: str, hint_level: int, student_input: str) -> tuple[bool, str]:
    """
    Calls the Gemini API to get the next Socratic hint based on the level.
    """
    
    # Handle requests with no student input (e.g. initial question or unconditional hint request)
    if not student_input:
        if hint_level == 0:
            student_input = "(No input yet. Please give me the level 0 guiding question.)"
        else:
            student_input = "(The student explicitly asked for the next hint without providing an answer. Please evaluate as UNDERSTOOD: no and provide the level {} hint.)".format(hint_level)

    system_prompt = f"""You are a Socratic tutor. Subject: {subject}
Question: {question}
Current hint level: {hint_level}

Hint level rules — follow STRICTLY, never reveal more than the current level allows:
- Level 0: Ask ONE question about their current approach or understanding. 
  Do not name any concept, formula, or technique.
- Level 1: Point out ONE specific gap or wrong assumption in the student's stated approach. Do NOT describe the correct mechanism, method, or reasoning — only point at what's missing, in the vaguest possible terms. If your hint could let the student solve it without further hints, it's too generous for Level 1.
- Level 2: Name the relevant concept/technique explicitly, but give no 
  worked steps or formula application.
- Level 3: Give a structural scaffold (pseudocode for coding/math, or a 
  guiding framework for conceptual subjects) — still not the final answer.
- Level 4: Give the full answer with a clear explanation of why it's correct.
IMPORTANT: If hint_level is 4, you MUST give the full answer and explanation regardless of the student's last message or your understanding assessment. Never ask the student to explain first at level 4 — always reveal."""

    if hint_level == 4:
        system_prompt += "\n\nGive the full explanation strictly matching level 4 now."
    else:
        system_prompt += f"""\n\nFirst, output exactly one line: "UNDERSTOOD: yes" or "UNDERSTOOD: no". 
Only mark UNDERSTOOD: yes if the student's message restates the actual concept, reasoning, or mechanism in their own words. Generic affirmations like 'I get it', 'okay', 'thanks', or 'got it' without substantive content do NOT count as understood — in that case, ask them to briefly explain it back before advancing.
Then, on the next lines, give ONE hint strictly matching level {hint_level}."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Student's last message: {student_input}")
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join([c.get("text", "") for c in content if isinstance(c, dict) and "text" in c])
        elif not isinstance(content, str):
            content = str(content)
        content = content.strip()
    except Exception as e:
        return False, f"Error calling Gemini: {e}"

    if hint_level == 4:
        # At Level 4, bypass understanding check entirely; the response is purely the hint text.
        return False, content

    # Parse response
    lines = content.split('\n')
    understood_line = lines[0].strip().upper()
    
    understood = False
    if "UNDERSTOOD: YES" in understood_line:
        understood = True
    
    # Join everything after the first line as the hint text
    hint_text = '\n'.join(lines[1:]).strip()
    
    # Fallback in case LLM does not put the flag on the first line
    if not hint_text:
        hint_text = content

    return understood, hint_text
