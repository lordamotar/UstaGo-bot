from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_faq_keyboard(questions: list, page: int = 0, page_size: int = 5, section: str = "client") -> InlineKeyboardMarkup:
    """
    Generates an inline keyboard for FAQ questions with pagination.
    """
    builder = InlineKeyboardBuilder()
    
    start_index = page * page_size
    end_index = start_index + page_size
    current_questions = questions[start_index:end_index]
    
    for i, q in enumerate(current_questions):
        # Use the global index of the question for callback data
        q_idx = start_index + i
        # Truncate long questions if necessary for button text
        text = q['question']
        if len(text) > 40:
            text = text[:37] + "..."
        builder.row(InlineKeyboardButton(text=text, callback_data=f"faq_q:{section}:{q_idx}"))
    
    # Pagination row
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"faq_p:{section}:{page-1}"))
    
    total_pages = (len(questions) + page_size - 1) // page_size
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    
    if end_index < len(questions):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"faq_p:{section}:{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
        
    return builder.as_markup()

def get_back_to_faq_keyboard(section: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"faq_p:{section}:{page}")]
    ])
