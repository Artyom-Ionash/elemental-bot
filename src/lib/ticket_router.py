import re
from typing import Literal, TypedDict


class RoutingResult(TypedDict):
    action: Literal["dispatch_police", "dispatch_ambulance", "dispatch_fire", "auto_reply", "llm_triage"]
    reason: str
    reply_text: str | None


class TicketRouter:
    def __init__(self):
        # Регулярки для экстренной маршрутизации (Fast Path - Хардкорные правила)
        self.police_pattern = re.compile(r"(убивают|напал|оружие|пистолет|нож|драка|стрельба|ограбили)", re.IGNORECASE)
        self.medical_pattern = re.compile(r"(кровь|сердце|задыхается|без сознания|ранение|рожает|инфаркт)", re.IGNORECASE)
        self.fire_pattern = re.compile(r"(пожар|дым|горит|газ|взрыв|пламя)", re.IGNORECASE)

        # Мок базы знаний (Информационные запросы, не требующие оператора)
        self.faq_db = {
            "штраф": "По вопросам штрафов ГИБДД используйте портал Госуслуг.",
            "справочная": "Вы позвонили в службу экстренного реагирования. Для получения справочной информации наберите 122.",
            "кошка на дереве": "Служба спасения не выезжает для снятия животных с деревьев. Обратитесь в частные службы спасения.",
        }

    def route(self, text: str) -> RoutingResult:
        # 1. Экстренная маршрутизация (Risky / Escalation Path)
        if self.fire_pattern.search(text):
            return {"action": "dispatch_fire", "reason": "Угроза возгорания/взрыва", "reply_text": None}
        if self.medical_pattern.search(text):
            return {"action": "dispatch_ambulance", "reason": "Угроза жизни и здоровью", "reply_text": None}
        if self.police_pattern.search(text):
            return {"action": "dispatch_police", "reason": "Криминальная угроза", "reply_text": None}

        # 2. Нецелевые / Информационные запросы (Happy Path 1 - Auto Reply)
        text_lower = text.lower()
        for keyword, answer in self.faq_db.items():
            if keyword in text_lower:
                return {"action": "auto_reply", "reason": f"Non-emergency ({keyword})", "reply_text": answer}

        # 3. Неясный или сложный запрос -> передаем LLM-диспетчеру для триажа (Happy Path 2)
        return {"action": "llm_triage", "reason": "Triage Required", "reply_text": None}
