from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class CustomerCreate(BaseModel):
	name: str
	email: EmailStr
	phone_number: str
	date_of_birth: str

class CustomerResponse(BaseModel):
	id: int
	name: str
	email: str
	phone_number: str
	date_of_birth: str
	created_at: datetime

	class Config:
		from_attribute = True

class TransactionResponse(BaseModel):
	id: int
	date: datetime
	description: str
	amount: float
	category: Optional[str]
	subcategory: Optional[str]
	merchant: Optional[str]
	is_recurring: bool
	is_anomaly: bool
	confidence_score: Optional[float]

	# allows you to create the model from class instances or ORM objects not just dict
	# because of this we can do db.query on main.py
	class Config:
		from_attribute = True

class CreditCardResponse(BaseModel):
    id: int
    card_number_last_four: str
    bank_name: str
    card_type: str
    credit_limit: float
    current_balance: float
    minimum_payment: float
    due_date: str
    statement_date: str
    apr: float
    rewards_rate: float
    
    class Config:
        from_attributes = True

class AnomalyResponse(BaseModel):
    transaction_id: int
    anomaly_type: str
    score: float
    description: str

class DueDateResponse(BaseModel):
    credit_card_id: int
    bank_name: str
    due_date: str
    amount: float
    days_until_due: int

class CreditCardCreate(BaseModel):
    card_number_last_four: str
    bank_name: str
    card_type: str
    credit_limit: float
    current_balance: float
    minimum_payment: float
    due_date: str
    statement_date: str
    apr: float
    rewards_rate: float

class RewardAnalysisResponse(BaseModel):
    total_rewards_earned: float
    rewards_by_category: Dict[str, float]
    potential_rewards: float
    optimization_suggestions: List[str]

class SpendingInsightsResponse(BaseModel):
    monthly_spending: Dict[str, float]
    category_breakdown: Dict[str, float]
    trends: List[str]
    recommendations: List[str]