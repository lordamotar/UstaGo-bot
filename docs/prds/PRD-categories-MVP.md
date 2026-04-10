# PRD: Categories MVP & Master Registration
**Status**: Approved
**Author**: agency-product-manager  
**Last Updated**: 2026-04-01  
**Version**: 1.0

## 1. Problem Statement
To successfully launch "UstaGo" (Алматы-Мастер) in Almaty, we need a focused structural taxonomy of services that addresses the highest frequency and most critical daily needs of local residents. An overly complex list of categories will overwhelm clients and deter masters from completing registration. We need an MVP category tree that allows masters to accurately define their skills while keeping the client experience simple and intuitive.

**Evidence:**
- Fast adoption requires low cognitive load during onboarding.
- Local demand in Semey heavily skews towards household maintenance, cleaning, appliance repair, and moving services.

## 2. Goals & Success Metrics
| Goal | Metric | Current Baseline | Target | Measurement Window |
|------|--------|-----------------|--------|--------------------|
| High conversion to registration | Master funnel completion rate | 0% | > 70% | 30 days post-launch |
| Reduced categorisation errors | Support requests regarding categories | N/A | < 5% | 30 days post-launch |

## 3. Non-Goals
- We are not building an exhaustive list of all possible professions (e.g., Beauty, Pets, Construction) for v1. These will be added later post-MVP.
- We are not implementing a search bar for categories in v1; we rely strictly on an inline-button taxonomy.

## 4. User Personas & Stories
**Primary Personas**: 
- **Master**: Needs to quickly select applicable skills to start receiving relevant orders without noise.
- **Client**: Needs to quickly post a job to the exact relevant masters.

Core user stories with acceptance criteria:
**Story 1**: As a Master, I want to select one or multiple subcategories during registration so that I only receive relevant job requests.
**Acceptance Criteria**:
- [ ] Given the category selection step, when presented with the list, then the Master can toggle on/off multiple subcategories.
- [ ] Given the master has selected subcategories, when finishing registration, then these selections are saved to their profile.

## 5. Solution Overview
We will implement a two-tier nested category tree consisting of 4 top-level parents and specific high-demand child categories. 

### MVP Category Tree:
**🏠 1. Мастер на час**
- Электрик
- Сантехник
- Сборка мебели
- Вскрытие замков

**🧹 2. Клининг и уборка**
- Уборка квартир
- Химчистка (диваны, ковры)
- Мойка окон

**📱 3. Ремонт техники**
- Стиральные машины / холодильники
- Кондиционеры
- Компьютеры / смартфоны

**🚚 4. Грузоперевозки и авто**
- Грузоперевозки (Газель)
- Грузчики
- Шиномонтаж (выездной)

**Key Design Decisions:**
- Decision 1: We chose a multi-select modal interaction (inline Telegram keyboard with checkboxes `✅`/`❌`) over single-select because masters often provide multiple related services (e.g., Грузоперевозки + Грузчики).
- Decision 2: We are deferring the "More" section to v2 to focus entirely on the core liquid marketplace categories first.

## 6. Technical Considerations
- **Dependencies**: Telegram Inline Keyboard limitations (can't have too many buttons per row, usually max 2-3 for text readability). 
- **Data Schema**: Need a robust M:N mapping between `Masters` and `Subcategories`. 

## 7. Launch Plan
| Phase | Date | Audience | Success Gate |
|-------|------|----------|-------------|
| Internal alpha | TBD | Core team | Category schema implemented in DB and UI |
| GA rollout | TBD | Semey users | >50 masters successfully onboard and select categories |
