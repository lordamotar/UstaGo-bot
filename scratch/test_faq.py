from bot.utils.faq_manager import faq_manager

print(f"Sections found: {list(faq_manager.sections.keys())}")
client_qs = faq_manager.get_questions('client')
master_qs = faq_manager.get_questions('master')

print(f"Client questions: {len(client_qs)}")
for i, q in enumerate(client_qs[:2]):
    print(f"  {i+1}. {q['question']}")

print(f"Master questions: {len(master_qs)}")
for i, q in enumerate(master_qs[:2]):
    print(f"  {i+1}. {q['question']}")
