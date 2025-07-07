import email
import re
from typing import Dict, List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email_reply_parser import EmailReplyParser
from fastapi import UploadFile, HTTPException
import dateparser
from datetime import datetime

class EmailParser:
	def __init__(self):
		# credit_card_patterns is dict with key statement, transaction, payment and balance
		self.credit_card_patterns = {
			'statement': [
				r'statement', # using raw string treats backslashes literally and does not interpret
				r'monthly statement',
				r'credit card statement',
				r'billing statement'
			],
			'transaction': [
				r'transaction alert',
				r'purchase notification',
				r'transaction notification',
				r'spending alert'
			],
			'payment': [
				r'payment due',
				r'payment reminder',
				r'minimum payment',
				r'payment confirmation'
			],
			'balance': [
				r'balance alert',
				r'current balance',
				r'available credit',
				r'credit limit'
			]
		}

	async def parse_email(self, file: UploadFile) -> Dict:
		try:
			content = await file.read()
			# isinstance(object, classinfo), object is the variable or value u want to check with
			if isinstance(content, bytes):
				content = content.decode('utf-8', errors='ignore')
			msg = email.message_from_string(content)
			email_data = {
				'subject': msg.get('Subject', ''),
				'from': msg.get('From', ''),
				'to': msg.get('To', ''),
				'date': msg.get('Date', ''),
				'body': self.extract_body(msg),
				'attachments': self.extract_attachments(msg)
			}
			parsed_date = self.parse_date(email_data['date'])
			if parsed_date:
				email_data['parsed_date'] = parsed_date
			email_data['email_type'] = self.classify_email_type(email_data['subject'], email_data['body'])
			email_data['extracted_info'] = self.extract_financial_info(email_data['body'])
			return email_data
		except Exception as e:
			raise HTTPException(status_code=400, detail=f"Failed to parse email: {str(e)}")

	def extract_body(self, msg) ->str:
		body = ""
		if msg.is_multipart():
			for part in msg.walk():
				if part.get_content_type() == "text/plain":
					body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
				elif part.get_content_type() == "text/html":
					html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
					body += self.html_to_text(html_body)
		else:
			body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
		cleaned_body = EmailReplyParser.parse_reply(body)
		return cleaned_body

	def html_to_text(self, html: str) -> str:
		html = re.sub(r'<[^>]+>', '', html)
		html = re.sub(r'&nbsp;', ' ', html)
		html = re.sub(r'&amp;', '&', html)
		html = re.sub(r'&lt;', '<', html)
		html = re.sub(r'&gt;', '>', html)
		html = re.sub(r'&quot;', '"', html)
		return html

	def extract_attachments(self, msg) -> List[Dict]:
		attachments = []

		if msg.is_multipart():
			for part in msg.walk():
				if part.get_content_disposition() == 'attachment':
					filename = part.get_filename()
					if filename:
						attachments.append({
		                    'filename': filename,
		                    'content_type': part.get_content_type(),
		                    'size': len(part.get_payload(decode=True))
						})

		return attachments

	def parse_date(self, date_string: str) -> Optional[datetime]:
		try:
			if date_string:
				return dateparser.parse(date_string)
		except:
			pass
		return None

	def classify_email_type(self, subject: str, body: str) -> str:
		text_to_check = (subject + " " + body).lower()
		for email_type, patterns in self.credit_card_patterns.items():
			for pattern in patterns:
				if re.search(pattern, text_to_check):
					return email_type
		return 'unknown'

	def extract_financial_info(self, body: str) -> Dict:
		info = {}

		amount_patterns = [
			# AED 1,234.56 or DHS 1,234.56 or د.إ 1,234.56
		    r'(?:AED|DHS|د\.إ)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
			# 1,234.56 AED or DHS or dirhams
		    r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:AED|DHS|د\.إ|dirhams?)',
			# amount: AED 1,234.56 or DHS 1,234.56
		    r'amount:?\s*(?:AED|DHS|د\.إ)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
			# total: AED 1,234.56
		    r'total:?\s*(?:AED|DHS|د\.إ)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
			# balance: AED 1,234.56
		    r'balance:?\s*(?:AED|DHS|د\.إ)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
		]
		amounts = []
		for pattern in amount_patterns:
			matches = re.findall(pattern, body, re.IGNORECASE) # re is regular expression
			for match in matches:
				try:
					amount = float(match.replace(',', ''))
					amounts.append(amount)
				except ValueError:
					continue
		if amounts:
			info['amounts'] = amounts
			info['max_amount'] = max(amounts)
			info['min_amount'] = min(amounts)
		date_patterns = [
		    r'due\s+(?:on\s+)?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', # due on 10/02/2025
		    r'payment\s+due:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', # payment due date
		    r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', # matches date even if no label
		    r'(\w+\s+\d{1,2},?\s+\d{4})', # March 3, 2025
		]
		dates = []
		for pattern in date_patterns:
			matches = re.findall(pattern, body, re.IGNORECASE)
			for match in matches:
				parsed_date = dateparser.parse(match)
				if parsed_date:
					dates.append(parsed_date)
		if dates:
			info['dates'] = dates
			info['latest_date'] = max(dates)
			info['earliest_date'] = min(dates)
		merchant_patterns = [
		    r'merchant:?\s*([A-Za-z0-9\s&\-\.]+)',
		    r'at\s+([A-Za-z0-9\s&\-\.]+)',
		    r'purchase\s+at\s+([A-Za-z0-9\s&\-\.]+)',
		    r'transaction\s+at\s+([A-Za-z0-9\s&\-\.]+)',
		]
		merchants = []
		for pattern in merchant_patterns:
			matches = re.findall(pattern, body, re.IGNORECASE)
			merchants.extend([match.strip() for match in matches if len(match.strip()) > 2])
		if merchants:
			info['merchants'] = list(set(merchants))
		card_patterns = [
		    r'card\s+ending\s+in\s+(\d{4})',
		    r'card\s+\*+(\d{4})',
		    r'\*+(\d{4})',
		    r'xxxx\s*(\d{4})',
		]
		card_numbers = []
		for pattern in card_patterns:
			matches = re.findall(pattern, body, re.IGNORECASE)
			card_numbers.extend(matches)
		if card_numbers:
			info['card_last_four'] = list(set(card_numbers))
		return info

	def extract_transactions_from_email(self, email_data: Dict) -> List[Dict]:
		transactions = []

		if email_data.get('email_type') == 'transaction':
			extracted_info = email_data.get('extracted_info', {})
			# once u get the extracted info in dict above seperate them below on different list with the tag amounts, merchants, dates
			amounts = extracted_info.get('amounts', [])
			merchants = extracted_info.get('merchants', [])
			dates = extracted_info.get('dates', [])

			if amounts:
				transaction = {
					'amount': amounts[0],
					'date': dates[0] if dates else email_data.get('parsed_date'),
					'merchant': merchants[0] if merchants else 'Unknown',
					'description': f"Transaction from email: {email_data.get('subject', '')}",
					'raw_text': email_data.get('body', ''),
					'source': 'email'
		        }
				transactions.append(transaction)

		return transactions