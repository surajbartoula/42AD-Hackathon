import fitz
import pikepdf
import pytesseract
from PIL import Image
import io
import re
import os
from datetime import datetime
from typing import Optional, List
from fastapi import UploadFile, HTTPException
from models import Customer

# Fix OpenSSL legacy provider issue
os.environ['OPENSSL_CONF'] = '/dev/null'

class PDFParser:
	def __init__(self):
		self.password_attempts = []
		self.setup_openssl_config()
	
	def setup_openssl_config(self):
		"""Setup OpenSSL configuration to handle legacy encryption"""
		try:
			# Create a temporary OpenSSL config that enables legacy provider
			openssl_config = """
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect

[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1
"""
			# Write config to a temporary file
			import tempfile
			with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
				f.write(openssl_config)
				self.openssl_config_path = f.name
			
			# Set environment variable to use our config
			os.environ['OPENSSL_CONF'] = self.openssl_config_path
			print(f"DEBUG - OpenSSL config set to: {self.openssl_config_path}")
		except Exception as e:
			print(f"WARNING - Could not setup OpenSSL config: {e}")
			# Fallback: disable OpenSSL config entirely
			os.environ['OPENSSL_CONF'] = '/dev/null'

	def extract_birth_year(self, dob: str) -> Optional[str]:
		"""Extract birth year from various date formats"""
		if not dob:
			return None
		
		# Remove all non-digit characters
		dob_digits = re.sub(r'[^\d]', '', dob)
		
		if len(dob_digits) < 4:
			return None
		
		# Try different date formats
		formats_to_try = [
			'%Y-%m-%d',  # YYYY-MM-DD
			'%d-%m-%Y',  # DD-MM-YYYY
			'%m-%d-%Y',  # MM-DD-YYYY
			'%Y/%m/%d',  # YYYY/MM/DD
			'%d/%m/%Y',  # DD/MM/YYYY
			'%m/%d/%Y',  # MM/DD/YYYY
			'%Y%m%d',    # YYYYMMDD
			'%d%m%Y',    # DDMMYYYY
			'%m%d%Y',    # MMDDYYYY
		]
		
		for fmt in formats_to_try:
			try:
				parsed_date = datetime.strptime(dob, fmt)
				return str(parsed_date.year)
			except ValueError:
				continue
		
		# Fallback: try to extract 4-digit year from the string
		# Look for 4 consecutive digits that could be a year (1900-2100)
		year_pattern = r'(19|20)\d{2}'
		year_match = re.search(year_pattern, dob_digits)
		if year_match:
			return year_match.group()
		
		# If all else fails, check if first 4 digits could be a year
		if len(dob_digits) >= 4:
			potential_year = dob_digits[:4]
			if 1900 <= int(potential_year) <= 2100:
				return potential_year
		
		# Check if last 4 digits could be a year
		if len(dob_digits) >= 4:
			potential_year = dob_digits[-4:]
			if 1900 <= int(potential_year) <= 2100:
				return potential_year
		
		return None

	def generate_password_candidates(self, customer: Customer) -> List[str]:
		"""Generate password candidates with focus on birth year + phone format"""
		candidates = []
		name_parts = customer.name.lower().split()
		full_name = ''.join(name_parts)
		phone = re.sub(r'[^\d]', '', customer.phone_number)
		dob = customer.date_of_birth

		# Extract birth year properly
		birth_year = self.extract_birth_year(dob)

		# DEBUG: Print what we extracted
		print(f"DEBUG - Raw DOB: '{dob}'")
		print(f"DEBUG - Birth year extracted: '{birth_year}'")
		print(f"DEBUG - Raw phone: '{customer.phone_number}'")
		print(f"DEBUG - Phone digits: '{phone}'")
		print(f"DEBUG - Phone last 4: '{phone[-4:] if len(phone) >= 4 else 'N/A'}'")

		# PRIORITY: Add the specific format (birth year + last 4 phone digits) first
		if birth_year and len(phone) >= 4:
			primary_password = f"{birth_year}{phone[-4:]}"
			candidates.insert(0, primary_password)
			print(f"DEBUG - Primary password candidate: '{primary_password}'")
			
			# Add encoding variations for the primary password
			candidates.extend([
				primary_password,
				primary_password.encode('utf-8').decode('utf-8'),
				primary_password.encode('latin-1').decode('latin-1', errors='ignore'),
				str(primary_password).strip(),
			])

		# Add variations of birth year + phone combinations
		if birth_year and len(phone) >= 4:
			candidates.extend([
				f"{birth_year}{phone[-4:]}",
				f"{birth_year[-2:]}{phone[-4:]}",  # 2-digit year + last 4 phone
				f"{birth_year}{phone[-6:]}",       # year + last 6 phone digits
				f"{birth_year}{phone[-8:]}",       # year + last 8 phone digits
			])

		# Legacy date parsing for backward compatibility
		dob_digits = re.sub(r'[^\d]', '', dob)
		if len(dob_digits) >= 8:
			# Try different interpretations of date digits
			ddmm = dob_digits[6:8] + dob_digits[4:6]  # assuming YYYYMMDD
			ddmmyy = dob_digits[6:8] + dob_digits[4:6] + dob_digits[2:4]
			
			# Also try DD/MM/YYYY format
			if len(dob_digits) == 8:
				ddmm_alt = dob_digits[0:2] + dob_digits[2:4]  # assuming DDMMYYYY
				ddmmyy_alt = dob_digits[0:2] + dob_digits[2:4] + dob_digits[6:8]
				
				candidates.extend([
					f"{birth_year}{ddmm_alt}" if birth_year else '',
					f"{birth_year}{ddmmyy_alt}" if birth_year else '',
				])

		# Name derived combinations
		if len(full_name) >= 4:
			first4 = full_name[:4]
			last4 = full_name[-4:]
			
			if len(dob_digits) >= 8:
				ddmm = dob_digits[6:8] + dob_digits[4:6] if len(dob_digits) >= 8 else ''
				ddmmyy = dob_digits[6:8] + dob_digits[4:6] + dob_digits[2:4] if len(dob_digits) >= 8 else ''
				
				candidates.extend([
					f"{first4}{ddmmyy}",
					f"{first4}{ddmm}",
					f"{last4}{phone[-4:]}" if len(phone) >= 4 else '',
					f"{first4.upper()}{ddmm}",
					f"{first4.upper()}{ddmmyy}"
				])

		# Card derived combinations
		for card in customer.credit_cards:
			if hasattr(card, 'card_number_last_four'):
				if len(dob_digits) >= 8:
					ddmm = dob_digits[6:8] + dob_digits[4:6]
					candidates.append(f"{card.card_number_last_four}{ddmm}")

		# Date format variations
		dob_formats = [
			dob.replace('-', ''),
			dob.replace('/', ''),
			dob.replace('.', ''),
		]
		
		# Add 2-digit year versions
		for fmt in dob_formats:
			if len(fmt) >= 2:
				candidates.extend([
					fmt,
					fmt[-2:],  # last 2 digits
					fmt[-4:],  # last 4 digits
				])

		# Name variations
		for name_part in name_parts:
			if name_part:
				candidates.extend([
					name_part,
					name_part.capitalize(),
					name_part.upper(),
				])

		# Phone variations
		if len(phone) >= 4:
			candidates.extend([
				phone,
				phone[-4:],
				phone[-6:] if len(phone) >= 6 else '',
				phone[-8:] if len(phone) >= 8 else '',
			])

		# Name + date combinations
		for name_part in name_parts:
			if name_part:
				for dob_format in dob_formats:
					if dob_format:
						candidates.extend([
							f"{name_part}{dob_format}",
							f"{name_part.capitalize()}{dob_format}",
							f"{dob_format}{name_part}",
							f"{name_part}{dob_format[-4:]}" if len(dob_format) >= 4 else '',
							f"{name_part}{dob_format[-2:]}" if len(dob_format) >= 2 else '',
						])

		# Name + phone combinations
		for name_part in name_parts:
			if name_part and len(phone) >= 4:
				candidates.extend([
					f"{name_part}{phone[-4:]}",
					f"{name_part.capitalize()}{phone[-4:]}",
					f"{phone[-4:]}{name_part}",
				])

		# Additional birth year combinations
		if birth_year:
			candidates.extend([
				birth_year,
				birth_year[-2:],  # 2-digit year
			])
			
			# Birth year + name combinations
			for name_part in name_parts:
				if name_part:
					candidates.extend([
						f"{birth_year}{name_part}",
						f"{name_part}{birth_year}",
						f"{birth_year[-2:]}{name_part}",
						f"{name_part}{birth_year[-2:]}",
					])

		# Remove empty strings and duplicates while preserving order
		candidates = [c for c in candidates if c and c.strip()]
		candidates = list(dict.fromkeys(candidates))  # Remove duplicates while preserving order

		print(f"DEBUG - Generated {len(candidates)} total candidates")
		print(f"DEBUG - First 10 candidates: {candidates[:10]}")

		return candidates

	def try_password_protected_pdf(self, pdf_bytes: bytes, customer: Customer) -> Optional[str]:
		password_candidates = self.generate_password_candidates(customer)
		
		print(f"DEBUG - Attempting to unlock PDF with {len(password_candidates)} password candidates")
		
		for i, password in enumerate(password_candidates):
			print(f"DEBUG - Trying password {i+1}/{len(password_candidates)}: '{password}'")
			
			# Method 1: Try with pikepdf
			try:
				with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
					text_content = ""
					for page in pdf.pages:
						page_text = str(page)
						text_content += page_text + "\n"
					
					if text_content.strip():
						print(f"SUCCESS - PDF unlocked with pikepdf using password: '{password}'")
						return text_content
			except pikepdf.PasswordError:
				continue
			except Exception as e:
				print(f"WARNING - pikepdf failed with password '{password}': {str(e)}")
				
				# Method 2: Try with PyMuPDF as fallback
				try:
					doc = fitz.open(stream=pdf_bytes, filetype="pdf")
					if doc.needs_pass:
						auth_result = doc.authenticate(password)
						if auth_result:
							text_content = ""
							for page_num in range(len(doc)):
								page = doc[page_num]
								text_content += page.get_text() + "\n"
							doc.close()
							
							if text_content.strip():
								print(f"SUCCESS - PDF unlocked with PyMuPDF using password: '{password}'")
								return text_content
						doc.close()
				except Exception as pymupdf_error:
					print(f"WARNING - PyMuPDF also failed with password '{password}': {str(pymupdf_error)}")
					continue
		
		print("DEBUG - All password attempts failed")
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
			# First try to extract text normally
			text_content = self.extract_text_with_pymupdf(content)
			
			if not text_content.strip():
				# If no text found, try OCR
				text_content = self.extract_text_with_ocr(content)
			
			return text_content
		
		except Exception as e:
			print(f"DEBUG - Normal extraction failed: {str(e)}")
			print("DEBUG - Attempting password-protected PDF extraction")
			
			# If normal extraction fails, try password-protected PDF
			password_content = self.try_password_protected_pdf(content, customer)
			
			if password_content:
				return password_content
			
			# If password attempts fail, try OCR as last resort
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

# Test function to verify password generation
def test_password_generation():
	"""Test the password generation with your example"""
	class MockCustomer:
		def __init__(self):
			self.name = "John Doe"
			self.phone_number = "050 123 4567"
			self.date_of_birth = "15/03/1980"  # DD/MM/YYYY format
			self.credit_cards = []
	
	parser = PDFParser()
	customer = MockCustomer()
	candidates = parser.generate_password_candidates(customer)
	
	print("\n" + "="*50)
	print("PASSWORD GENERATION TEST")
	print("="*50)
	print(f"Customer Name: {customer.name}")
	print(f"Phone Number: {customer.phone_number}")
	print(f"Date of Birth: {customer.date_of_birth}")
	print(f"Generated {len(candidates)} candidates:")
	
	for i, candidate in enumerate(candidates[:20]):  # Show first 20
		print(f"{i+1:2d}. {candidate}")
	
	if len(candidates) > 20:
		print(f"... and {len(candidates) - 20} more candidates")
	
	# Check if the expected password is in the list
	expected = "19804567"
	if expected in candidates:
		print(f"\n✅ Expected password '{expected}' found at position {candidates.index(expected) + 1}")
	else:
		print(f"\n❌ Expected password '{expected}' NOT found")
	
	print("="*50)

# Run the test if this file is executed directly
if __name__ == "__main__":
	test_password_generation()