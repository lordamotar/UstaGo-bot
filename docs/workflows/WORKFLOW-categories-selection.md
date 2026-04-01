# WORKFLOW: Master Category Selection & Order Routing
**Version**: 0.1
**Date**: 2026-04-01
**Author**: agency-workflow-architect
**Status**: Draft
**Implements**: Master Registration Flow & Order Dispatch

## Overview
This workflow defines how a Master interacts with the inline category keyboard to select their services, and how the system subsequently routes a new client order only to the Masters who selected the matching subcategory.

## Actors
| Actor | Role in this workflow |
|---|---|
| Master | Interacts with the category selection UI |
| Telegram Bot API | Sends UI updates and receives callback queries |
| Backend Service | Manages state, updates DB, dispatches orders |
| Database | Persists master_categories mapping |

## Handoff Contracts

### Backend -> Telegram Bot (Update Keyboard)
**Endpoint**: `editMessageText`
**Payload**:
```json
{
  "chat_id": 12345,
  "message_id": 6789,
  "text": "Выберите категории (можно несколько):",
  "reply_markup": {
    "inline_keyboard": [
      [{"text": "✅ Электрик", "callback_data": "cat_toggle:1"}],
      [{"text": "❌ Сантехник", "callback_data": "cat_toggle:2"}],
      [{"text": "💾 Сохранить", "callback_data": "cat_save"}]
    ]
  }
}
```

## Workflow Tree

### STEP 1: Categories Display
**Actor**: Backend Service
**Trigger**: Master reaches the category selection step of the registration FSM.
**Action**: Fetch all available categories, build an inline keyboard with pagination (if parent view) or a direct list of subcategories grouped by parent. Since we have ~13 subcategories, we can display them in a paginated list or accordion style. 
For UX optimization in Telegram: Show parent categories first. Clicking a parent expands/shows its subcategories with toggle states.
**Output on SUCCESS**: Telegram message sent with inline keyboard. -> GO TO STEP 2

### STEP 2: Category Toggle (Multi-select)
**Actor**: Master -> Telegram Bot API -> Backend Service
**Trigger**: Master clicks an inline button (e.g., `cat_toggle:id`).
**Action**: 
- Backend intercepts `callback_query`.
- Toggles the selected ID in the master's active temporary state (Redis/FSM memory).
- Regenerates the inline keyboard markup, replacing `❌` with `✅` (or vice versa) for that button.
- Calls `editMessageReplyMarkup` to update the message in place.
**Output on SUCCESS**: Keyboard updated visibly. -> WAIT FOR MORE CLICKS OR SAVE
**Output on FAILURE**: 
  - `FAILURE(timeout)`: Telegram API lag -> State unaffected, handle 429 Too Many Requests by dropping duplicate updates.

### STEP 3: Save Categories
**Actor**: Master -> Backend Service
**Trigger**: Master clicks "💾 Готово / Сохранить" (`cat_save`).
**Action**: 
- Validates at least 1 category is selected. 
- If 0, sends an alert (`answerCallbackQuery` with `show_alert=true`: "Выберите хотя бы одну категорию!").
- If >= 1, clears temporary FSM memory and shifts to the next registration step (e.g., "Upload Photos"). The actual DB persist might happen at the final `/complete_registration` step or here depending on DB design.
**Output on SUCCESS**: Proceeds to next registration step. -> END OF CATEGORY SELECTION

### STEP 4: Order Routing (Dispatch)
**Actor**: Backend Service
**Trigger**: A Client finishes creating a new Order and selects exactly 1 target subcategory (e.g., "Сантехник" ID=2).
**Action**: 
- Backend queries DB: `SELECT master_id FROM master_category_subscriptions JOIN masters ON ... WHERE subcategory_id = 2 AND masters.status = 'approved'`
- Iterates over active `master_id`s and dispatches the Order message to them asynchronously.
**Output on SUCCESS**: Messages sent to relevant masters.

## State Transitions
```
[registration_categories] -> (toggles) -> [registration_categories]
[registration_categories] -> (save clicked, count > 0) -> [registration_photos] (or similar next step)
```

## Assumptions
- A1: FSM state is temporarily saved in memory (Local/Redis) until the master formally finishes the complete flow to avoid broken DB artifacts.
- A2: Clients will select one specific subcategory per order.
- A3: The display limit on Telegram is handled by UI slicing. Max 8 rows per message is appropriate.
