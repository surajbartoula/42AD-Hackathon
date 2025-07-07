from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn

from database import SessionLocal, engine, Base
from models import Customer, Transaction, CreditCard
from services.pdf_parser import PDFParser
from services.email_parser import EmailParser
from services.transaction_extractor import TransactionExtractor
from services.categorizer import TransactionCategorizer
from services.anomaly_detector import AnomalyDetector
from services.reminder_service import ReminderService
from services.reward_analyzer import RewardAnalyzer
from schemas import CustomerCreate, CustomerResponse, TransactionResponse, CreditCardResponse, CreditCardCreate

# Create database based on databas.py
Base.metadata.create_all(bind=engine)

app	= FastAPI(
	title="42 Abu Dhabi Hackathon",
	description="API for parsing credit card statements and managing payments",
	version="1.0.0"
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"], 		# Allow requests from any origin (public API)
	allow_credentials=True, 	# Allow cookies/auth headers in requests
	allow_methods=["*"],		# Allow all HTTP methods (GET, POST, PUT, DELETE, etc)
	allow_headers=["*"],		# Allow all headers (like Authorization, Content-Type)
)

# finally runs even though error happened
def get_db():
	db = SessionLocal()
	try:
		yield db # yield someone car and when they return it u take it back and finally: park
	finally:
		db.close()

@app.get("/")
async def root():
	return {"message": "Credit Card Management API"}

@app.post("/customers/", response_model=CustomerResponse)
async def create_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
	db_customer = Customer(**customer.dict())
	db.add(db_customer)
	db.commit()
	db.refresh(db_customer)
	return db_customer

@app.post("/upload-pdf/{customer_id}")
async def upload_pdf(
	customer_id: int,
	file: UploadFile = File(...),
	db: Session = Depends(get_db)
):
	if not file.filename.endswith('.pdf'):
		raise HTTPException(status_code=400, detail="Only PDF files are allowed")
	customer = db.query(Customer).filter(Customer.id == customer_id).first()
	if not customer:
		raise HTTPException(status_code=404, detail="Customer not found")
	try:
		pdf_parser = PDFParser()
		content = await pdf_parser.parse_pdf(file, customer)
		transaction_extractor = TransactionExtractor()
		transactions = transaction_extractor.extract_transactions(content)
		if not transactions:
			return {"message": "No transcations found in the PDF", "transactions_processed": 0}
		categorizer = TransactionCategorizer()
		categorized_transactions = categorizer.categorize_transactions(transactions)
		for transaction_data in categorized_transactions:
			transaction = Transaction(
				customer_id=customer_id,
				date=transaction_data.get('date'),
				description=transaction_data.get('description'),
				amount=transaction_data.get('amount'),
				category=transaction_data.get('category'),
				subcategory=transaction_data.get('subcategory'),
				merchant=transaction_data.get('merchant'),
				is_recurring=transaction_data.get('is_recurring', False),
				confidence_score=transaction_data.get('confidence_score'),
				raw_text=transaction_data.get('raw_text')
			)
			db.add(transaction)
		db.commit()
		return {"message": f"Processed {len(categorized_transactions)} transactions", "transactions_processed": len(categorized_transactions)}
	except Exception as e:
		db.rollback()
		raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/upload-email/{customer_id}")
async def upload_email(
	customer_id: int,
	file: UploadFile = File(...),
	db: Session = Depends(get_db)
):
	if not file.filename.endswith('./eml'):
		raise HTTPException(status_code=400, detail="Only EML email files are allowed")
	customer = db.query(Customer).filter(Customer.id == customer_id).first()
	if not customer:
		raise HTTPException(status_code=404, detail="Customer not found")
	try:
		email_parser = EmailParser()
		content = await email_parser.parse_email(file)
		transaction_extractor = TransactionExtractor()
		transactions = transaction_extractor.extract_transactions(content)
		if not transactions:
			return {"message": "No transactions found in the email", "transactions_processed": 0}
		categorizer = TransactionCategorizer()
		categorized_transactions = categorizer.categorize_transactions(transactions)
		for transaction_data in categorized_transactions:
			transaction = Transaction(
				customer_id=customer_id,
				date=transaction_data.get('date'),
				description=transaction_data.get('description'),
				amount=transaction_data.get('amount'),
				category=transaction_data.get('category'),
				subcategory=transaction_data.get('subcategory'),
				merchant=transaction_data.get('merchant'),
				is_recurring=transaction_data.get('is_recurring', False),
				confidence_score=transaction_data.get('confidence_score'),
				raw_text=transaction_data.get('raw_text')
			)
			db.add(transaction)
		
		db.commit()
		return {"message": f"Processed {len(categorized_transactions)} transactions", "transactions_processed": len(categorized_transactions)}
	except Exception as e:
		db.rollback()
		raise HTTPException(status_code=500, detail=f"Error processing email: {str(e)}")

@app.get("/customers/{customer_id}/transactions", response_model=List[TransactionResponse])
async def get_transactions(customer_id: int, db: Session = Depends(get_db)):
	transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).all()
	return transactions

@app.get("/customers/{customer_id}/anomalies")
async def detect_anomalies(customer_id: int, db: Session = Depends(get_db)):
	customer = db.query(Customer).filter(Customer.id == customer_id).first()
	if not customer:
		raise HTTPException(status_code=404, detail="Customer not found")
	transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).all()
	if not transactions:
		return {"anomalies": [], "message": "No transactions found for analysis"}
	try:
		anomaly_detector = AnomalyDetector()
		anomalies = anomaly_detector.detect_anomalies(transactions)
		return {"anomalies": anomalies, "total_anomalies": len(anomalies)}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error detecting anomalies: {str(e)}")

@app.get("/customers/{customer_id}/due-dates")
async def get_due_dates(customer_id: int, db: Session = Depends(get_db)):
	reminder_service = ReminderService()
	due_dates = reminder_service.get_upcoming_due_dates(customer_id, db)
	return {"due_dates": due_dates}

@app.post("/customers/{customer_id}/credit-cards", response_model=CreditCardResponse)
async def create_credit_card(
    customer_id: int,
    card_data: CreditCardCreate,
    db: Session = Depends(get_db)
):
	customer = db.query(Customer).filter(Customer.id == customer_id).first()
	if not customer:
		raise HTTPException(status_code=404, detail="Customer not found")
	credit_card = CreditCard(customer_id=customer_id, **card_data.dict()) # **card_data.dict() unpacks the dictionery
	db.add(credit_card)
	db.commit()
	db.refresh(credit_card)
	return credit_card

@app.get("/customers/{customer_id}/credit-cards", response_model=List[CreditCardResponse])
async def get_credit_cards(customer_id: int, db: Session = Depends(get_db)):
	credit_cards = db.query(CreditCard).filter(CreditCard.customer_id == customer_id).all()
	return credit_cards

@app.get("/customers/{customer_id}/rewards")
async def get_rewards_analysis(customer_id: int, db: Session = Depends(get_db)):
	customer = db.query(Customer).filter(Customer.id == customer_id).first()
	if not customer:
		raise HTTPException(status_code=404, detail="Customer not found")
	transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).all()
	credit_cards = db.query(CreditCard).filter(CreditCard.customer_id == customer_id).all()
	if not transactions:
		return {"rewards_analysis": {}, "message": "No transactions found for analysis"}
	try:
		reward_analyzer = RewardAnalyzer()
		analysis = reward_analyzer.analyze_rewards(transactions, credit_cards)
		return {"rewards_analysis": analysis}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error analyzing rewards: {str(e)}")

@app.get("/customers/{customer_id}/spending-insights")
async def get_spending_insights(customer_id: int, db: Session = Depends(get_db)):
	transactions = db.query(Transaction).filter(Transaction.customer_id == customer_id).all()
	credit_cards = db.query(CreditCard).filter(CreditCard.customer_id == customer_id).all()
	reward_analyzer = RewardAnalyzer()
	insights = reward_analyzer.generate_spending_insights(transactions, credit_cards)
	return {"spending_insights": insights}

if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)