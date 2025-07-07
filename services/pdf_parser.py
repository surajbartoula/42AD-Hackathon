import fitz
import pikepdf
import pytesseract
from PIL import Image
import io
import re
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from models import Customer

class PDFParser:
	def __init__(self):
		self.password_attempts = []

	def generate_password_candidates(self, customer: Customer) -> list[str]:
		candidates = []
		name_parts = customer.name.lower().split()
		full_name = ''.join(name_parts)
		phone = re.sub(r'[^\d]', '', customer.phone_number) # if not number replace with '' in phone number
		dob = customer.date_of_birth

		#normalize DOB
		dob_digits = re.sub(r'[^\d]', '', dob)
		ddmm = dob_digits[6:8] + dob_digits[4:6] if len(dob_digits) >= 8 else ''
		ddmmyy = dob_digits[6:8] + dob_digits[4:6] + dob_digits[2:4] if len(dob_digits) >= 8 else ''
		#name derived combinations
		first4 = full_name[:4]
		last4 = full_name[-4:]
		candidates.extend([
			f"{first4}{ddmmyy}",
			f"{first4}{ddmm}",
			f"{last4}{phone[-4:]}" if len(phone) >= 4 else '',
			f"{first4.upper()}{ddmm}",
			f"{first4.upper()}{ddmmyy}"
		])
		#card derived combinations
		for card in customer.credit_cards:
			candidates.append(f"{card.card_number_last_four}{ddmm}") #not sure will work will check later
		dob_formats = [
			dob.replace('-', ''),
			dob.replace('/', ''),
			dob.replace('-', '')[-2:],
			dob.replace('/', '')[-2:],
		]
		for name_part in name_parts:
			candidates.extend([
				name_part,
				name_part.capitalize(),
				name_part.upper(),
			])
		candidates.extend([
			phone,
			phone[-4:],
			phone[-6:],
			phone[-8:],
		])
		candidates.extend(dob_formats)
		for name_part in name_parts:
			for dob_format in dob_formats:
				candidates.extend([
					f"{name_part}{dob_format}",
					f"{name_part.capitalize()}{dob_format}",
					f"{dob_format}{name_part}",
				])
		for name_part in name_parts:
			candidates.extend([
				f"{name_part}{phone[-4:]}",
				f"{name_part.capitalize()}{phone[-4:]}",
				f"{phone[-4:]}{name_part}",
			])
		return list(set(candidates))

	def try_password_protected_pdf(self, pdf_bytes: bytes, customer: Customer) -> Optional[str]:
		password_candidates = self.generate_password_candidates(customer)
		for password in password_candidates:
			try:
				with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
					text_content = ""
					for page in pdf.pages:
						page_text = str(page)
						text_content += page_text + "\n"
					# .strip remove any leading & trailing whitespace characters
					if text_content.strip():
						return text_content
			except pikepdf.PasswordError:
				continue
			except Exception as e:
				continue
		return None

	def extract_text_with_pymupdf(self, pdf_bytes: bytes) -> str:
		try:
			doc = fitz.open(stream=pdf_bytes, filetype="pdf")
			text_content = ""
			for page_num in range(len(doc)):
				page = doc[page_num]
				text_content += page.get_text() + "\n"
			doc.close()
			return text_content
		except Exception as e:
			raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")

	def extract_text_with_ocr(self, pdf_bytes: bytes) -> str:
		try:
			doc = fitz.open(stream=pdf_bytes, filetype="pdf")
			text_content = ""
			
			for page_num in range(len(doc)):
				page = doc[page_num]
				# key diff here pymuf vs ocr get_pixmap renders the entire page as an image
				pix = page.get_pixmap()
				img_data = pix.tobytes("png")
				
				img = Image.open(io.BytesIO(img_data))
				
				ocr_text = pytesseract.image_to_string(img, config='--psm 6')
				text_content += ocr_text + "\n"
			
			doc.close()
			return text_content
		except Exception as e:
			raise HTTPException(status_code=400, detail=f"Failed to perform OCR on PDF: {str(e)}")

	# Handling pdf file parsing in a robust, fallback-based way. supports normal pdf with
	# with embeded text, image based pdf, password protected pdf and FastAPI UploadFile handling
	async def parse_pdf(self, file: UploadFile, customer: Customer) -> str:
		if file.content_type != "application/pdf":
			raise HTTPException(status_code=400, detail="File must be a PDF")
		
		content = await file.read()
		
		try:
			text_content = self.extract_text_with_pymupdf(content)
			
			if not text_content.strip():
				text_content = self.extract_text_with_ocr(content)
			
			return text_content
		
		except Exception as e:
			password_content = self.try_password_protected_pdf(content, customer)
			
			if password_content:
				return password_content
			
			try:
				text_content = self.extract_text_with_ocr(content)
				return text_content
			except Exception as ocr_error:
				raise HTTPException(
					status_code=400, 
					detail=f"Failed to parse PDF. Could not extract text or decrypt: {str(e)}"
				)

	def clean_extracted_text(self, text: str) -> str:
		lines = text.split('\n')
		cleaned_lines = []
		
		for line in lines:
			line = line.strip()
			if line and len(line) > 2:
				cleaned_lines.append(line)
		
		return '\n'.join(cleaned_lines)