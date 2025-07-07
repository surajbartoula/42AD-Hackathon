from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from models import Customer, CreditCard, PaymentReminder, Transaction
import dateparser
import re

class ReminderService:
    def __init__(self):
        self.due_date_patterns = [
            r'payment\s+due:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'due\s+date:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'due\s+on:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'payment\s+due\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'due\s+(\w+\s+\d{1,2},?\s+\d{4})',
            r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})\s+due',
        ]
        
        self.minimum_payment_patterns = [
            r'minimum\s+payment:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'min\s+payment:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'minimum\s+due:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'amount\s+due:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        self.balance_patterns = [
            r'current\s+balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'new\s+balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'statement\s+balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
    
    def extract_due_date_from_text(self, text: str) -> Optional[datetime]:
        for pattern in self.due_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = dateparser.parse(date_str)
                if parsed_date:
                    return parsed_date
        return None
    
    def extract_minimum_payment_from_text(self, text: str) -> Optional[float]:
        for pattern in self.minimum_payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue
        return None
    
    def extract_balance_from_text(self, text: str) -> Optional[float]:
        for pattern in self.balance_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue
        return None
    
    def update_credit_card_info(self, credit_card: CreditCard, extracted_text: str, db: Session):
        due_date = self.extract_due_date_from_text(extracted_text)
        minimum_payment = self.extract_minimum_payment_from_text(extracted_text)
        current_balance = self.extract_balance_from_text(extracted_text)
        
        if due_date:
            credit_card.due_date = due_date.strftime('%Y-%m-%d')
        
        if minimum_payment:
            credit_card.minimum_payment = minimum_payment
        
        if current_balance:
            credit_card.current_balance = current_balance
        
        db.commit()
    
    def create_payment_reminder(self, credit_card: CreditCard, db: Session) -> PaymentReminder:
        if not credit_card.due_date:
            return None
        
        due_date = datetime.strptime(credit_card.due_date, '%Y-%m-%d')
        
        existing_reminder = db.query(PaymentReminder).filter(
            PaymentReminder.credit_card_id == credit_card.id,
            PaymentReminder.due_date == due_date,
            PaymentReminder.reminder_sent == False
        ).first()
        
        if existing_reminder:
            return existing_reminder
        
        reminder = PaymentReminder(
            customer_id=credit_card.customer_id,
            credit_card_id=credit_card.id,
            due_date=due_date,
            amount=credit_card.minimum_payment or 0
        )
        
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        
        return reminder
    
    def get_upcoming_due_dates(self, customer_id: int, db: Session, days_ahead: int = 7) -> List[Dict]:
        today = datetime.now().date()
        future_date = today + timedelta(days=days_ahead)
        
        credit_cards = db.query(CreditCard).filter(
            CreditCard.customer_id == customer_id
        ).all()
        
        due_dates = []
        
        for card in credit_cards:
            if card.due_date:
                try:
                    due_date = datetime.strptime(card.due_date, '%Y-%m-%d').date()
                    
                    if today <= due_date <= future_date:
                        days_until_due = (due_date - today).days
                        
                        due_dates.append({
                            'credit_card_id': card.id,
                            'bank_name': card.bank_name,
                            'card_last_four': card.card_number_last_four,
                            'due_date': due_date.isoformat(),
                            'minimum_payment': card.minimum_payment or 0,
                            'current_balance': card.current_balance or 0,
                            'days_until_due': days_until_due,
                            'urgency': self._calculate_urgency(days_until_due)
                        })
                except ValueError:
                    continue
        
        return sorted(due_dates, key=lambda x: x['days_until_due'])
    
    def _calculate_urgency(self, days_until_due: int) -> str:
        if days_until_due <= 1:
            return 'critical'
        elif days_until_due <= 3:
            return 'high'
        elif days_until_due <= 7:
            return 'medium'
        else:
            return 'low'
    
    def get_overdue_payments(self, customer_id: int, db: Session) -> List[Dict]:
        today = datetime.now().date()
        
        credit_cards = db.query(CreditCard).filter(
            CreditCard.customer_id == customer_id
        ).all()
        
        overdue_payments = []
        
        for card in credit_cards:
            if card.due_date:
                try:
                    due_date = datetime.strptime(card.due_date, '%Y-%m-%d').date()
                    
                    if due_date < today:
                        days_overdue = (today - due_date).days
                        
                        overdue_payments.append({
                            'credit_card_id': card.id,
                            'bank_name': card.bank_name,
                            'card_last_four': card.card_number_last_four,
                            'due_date': due_date.isoformat(),
                            'minimum_payment': card.minimum_payment or 0,
                            'current_balance': card.current_balance or 0,
                            'days_overdue': days_overdue,
                            'late_fees_estimated': self._estimate_late_fees(days_overdue, card.minimum_payment or 0)
                        })
                except ValueError:
                    continue
        
        return sorted(overdue_payments, key=lambda x: x['days_overdue'], reverse=True)
    
    def _estimate_late_fees(self, days_overdue: int, minimum_payment: float) -> float:
        if days_overdue <= 0:
            return 0
        
        base_late_fee = 39.00
        
        if minimum_payment < 100:
            base_late_fee = 29.00
        elif minimum_payment > 500:
            base_late_fee = 49.00
        
        return base_late_fee
    
    def generate_reminder_message(self, due_date_info: Dict) -> str:
        days_until_due = due_date_info['days_until_due']
        bank_name = due_date_info['bank_name']
        minimum_payment = due_date_info['minimum_payment']
        due_date = due_date_info['due_date']
        
        if days_until_due == 0:
            return f"🚨 URGENT: Your {bank_name} credit card payment of ${minimum_payment:.2f} is due TODAY ({due_date})"
        elif days_until_due == 1:
            return f"⚠️ REMINDER: Your {bank_name} credit card payment of ${minimum_payment:.2f} is due TOMORROW ({due_date})"
        elif days_until_due <= 3:
            return f"📅 REMINDER: Your {bank_name} credit card payment of ${minimum_payment:.2f} is due in {days_until_due} days ({due_date})"
        else:
            return f"💳 Upcoming: Your {bank_name} credit card payment of ${minimum_payment:.2f} is due in {days_until_due} days ({due_date})"
    
    def mark_reminder_sent(self, reminder_id: int, db: Session):
        reminder = db.query(PaymentReminder).filter(PaymentReminder.id == reminder_id).first()
        if reminder:
            reminder.reminder_sent = True
            db.commit()
    
    def get_payment_history_analysis(self, customer_id: int, db: Session) -> Dict:
        transactions = db.query(Transaction).filter(
            Transaction.customer_id == customer_id,
            Transaction.description.ilike('%payment%')
        ).all()
        
        if not transactions:
            return {
                'total_payments': 0,
                'average_payment': 0,
                'payment_frequency': 'Unknown',
                'on_time_percentage': 0
            }
        
        payment_amounts = [t.amount for t in transactions]
        
        analysis = {
            'total_payments': len(transactions),
            'total_amount_paid': sum(payment_amounts),
            'average_payment': sum(payment_amounts) / len(payment_amounts),
            'largest_payment': max(payment_amounts),
            'smallest_payment': min(payment_amounts),
            'recent_payments': sorted(transactions, key=lambda x: x.date, reverse=True)[:5]
        }
        
        return analysis
    
    def suggest_payment_optimization(self, credit_card: CreditCard, transactions: List[Transaction]) -> Dict:
        if not credit_card.current_balance or credit_card.current_balance <= 0:
            return {'message': 'No balance to optimize'}
        
        current_balance = credit_card.current_balance
        minimum_payment = credit_card.minimum_payment or 0
        apr = credit_card.apr or 0.1999
        monthly_rate = apr / 12
        
        suggestions = {
            'current_situation': {
                'balance': current_balance,
                'minimum_payment': minimum_payment,
                'apr': apr * 100
            },
            'optimization_strategies': []
        }
        
        if minimum_payment > 0:
            months_minimum = self._calculate_payoff_time(current_balance, minimum_payment, monthly_rate)
            interest_minimum = self._calculate_total_interest(current_balance, minimum_payment, monthly_rate)
            
            suggestions['minimum_payment_scenario'] = {
                'months_to_payoff': months_minimum,
                'total_interest': interest_minimum,
                'total_paid': current_balance + interest_minimum
            }
        
        optimized_payment = max(minimum_payment * 2, 100)
        months_optimized = self._calculate_payoff_time(current_balance, optimized_payment, monthly_rate)
        interest_optimized = self._calculate_total_interest(current_balance, optimized_payment, monthly_rate)
        
        suggestions['optimized_payment_scenario'] = {
            'monthly_payment': optimized_payment,
            'months_to_payoff': months_optimized,
            'total_interest': interest_optimized,
            'total_paid': current_balance + interest_optimized,
            'interest_saved': interest_minimum - interest_optimized if minimum_payment > 0 else 0
        }
        
        return suggestions
    
    def _calculate_payoff_time(self, balance: float, payment: float, monthly_rate: float) -> int:
        if payment <= balance * monthly_rate:
            return 999
        
        months = 0
        remaining = balance
        
        while remaining > 0 and months < 600:
            interest = remaining * monthly_rate
            principal = payment - interest
            remaining -= principal
            months += 1
        
        return months
    
    def _calculate_total_interest(self, balance: float, payment: float, monthly_rate: float) -> float:
        if payment <= balance * monthly_rate:
            return float('inf')
        
        total_interest = 0
        remaining = balance
        
        while remaining > 0:
            interest = remaining * monthly_rate
            principal = payment - interest
            total_interest += interest
            remaining -= principal
        
        return total_interest