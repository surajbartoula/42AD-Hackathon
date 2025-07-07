from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

# inherit from Base class which is the SQLAlchemy base class created by declarative_base()
class Customer(Base):
	__tablename__ = "customers"
	# Foreign key referencing the id in the customers table (linking card to its owner).
	id = Column(Integer, primary_key=True, index=True)
	name = Column(String, index=True)
	email = Column(String, unique=True, index=True)
	phone_number = Column(String)
	date_of_birth = Column(String)
	created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
	transactions = relationship("Transaction", back_populates="customer")
	credit_cards = relationship("CreditCard", back_populates="customer")

class CreditCard(Base):
	__tablename__ = "credit_cards"
	id = Column(Integer, primary_key=True, index=True)
	customer_id = Column(Integer, ForeignKey("customers.id"))
	card_number_last_four = Column(String)
	bank_name = Column(String)
	card_type = Column(String)
	credit_limit = Column(Float)
	current_balance = Column(Float)
	minimum_payment = Column(Float)
	due_date = Column(String)
	statement_date = Column(String)
	apr = Column(Float)
	rewards_rate = Column(Float)
	created_at = Column(DateTime, default=datetime.utcnow)

	# Defines a many-to-one relationship: many credit cards belong to one customer.
	customer = relationship("Customer", back_populates="credit_cards")
	transactions = relationship("Transaction", back_populates="credit_card")

class Transaction(Base):
	__tablename__ = "transactions"

	id = Column(Integer, primary_key=True, index=True)
	customer_id = Column(Integer, ForeignKey("customers.id"))
	credit_card_id = Column(Integer, ForeignKey("credit_cards.id"), nullable=True)
	date = Column(DateTime)
	description = Column(Text)
	amount = Column(Float)
	category = Column(String)
	subcategory = Column(String)
	merchant = Column(String)
	is_recurring = Column(Boolean, default=False)
	is_anomaly = Column(Boolean, default=False)
	confidence_score = Column(Float)
	raw_text = Column(Text)
	created_at = Column(DateTime, default=datetime.utcnow)

	customer = relationship("Customer", back_populates="transactions")
	credit_card = relationship("CreditCard", back_populates="transactions")

class PaymentReminder(Base):
	__tablename__ = "payment_reminders"

	id = Column(Integer, primary_key=True, index=True)
	customer_id = Column(Integer, ForeignKey("customers.id"))
	credit_card_id = Column(Integer, ForeignKey("credit_cards.id"))
	due_date = Column(DateTime)
	amount = Column(Float)
	reminder_sent = Column(Boolean, default=False)
	created_at = Column(DateTime, default=datetime.utcnow)

class CategoryRule(Base):
	__tablename__ = "category_rules"

	id = Column(Integer, primary_key=True, index=True)
	pattern = Column(String)
	category = Column(String)
	subcategory = Column(String)
	confidence = Column(Float)
	created_at = Column(DateTime, default=datetime.utcnow)