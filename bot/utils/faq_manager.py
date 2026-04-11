import os
import re

class FAQManager:
    def __init__(self, file_path="FAQ.md"):
        self.file_path = file_path
        self.sections = {}
        self.load_faq()

    def load_faq(self):
        if not os.path.exists(self.file_path):
            # Try absolute path or project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.file_path = os.path.join(base_dir, "FAQ.md")
            if not os.path.exists(self.file_path):
                return

        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split by sections starting with ##
        sections_raw = re.split(r'^##\s+', content, flags=re.MULTILINE)
        
        for sec_raw in sections_raw[1:]:
            lines = sec_raw.split('\n')
            section_name = lines[0].strip()
            
            questions = []
            # Split by questions starting with ###
            questions_raw = re.split(r'^###\s+', '\n'.join(lines[1:]), flags=re.MULTILINE)
            
            for q_raw in questions_raw[1:]:
                q_lines = q_raw.split('\n')
                question_text = q_lines[0].strip()
                answer_text = '\n'.join(q_lines[1:]).strip()
                if question_text and answer_text:
                    questions.append({
                        "question": question_text,
                        "answer": answer_text
                    })
            
            # Identify section
            if "заказчиков" in section_name.lower():
                key = "client"
            elif "мастеров" in section_name.lower():
                key = "master"
            else:
                key = "all"
                
            self.sections[key] = {
                "name": section_name,
                "questions": questions
            }

    def get_questions(self, section_key):
        """Returns questions for a section, including 'all' section."""
        questions = self.sections.get(section_key, {}).get("questions", []).copy()
        if section_key != "all":
            all_questions = self.sections.get("all", {}).get("questions", [])
            questions.extend(all_questions)
        return questions

# Singleton instance
faq_manager = FAQManager()
