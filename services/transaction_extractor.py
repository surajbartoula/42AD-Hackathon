import re
import dateparser
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

class TransactionExtractor:
    def __init__(self):
        self.transaction_patterns = {
            'date': [
                r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})',
                r'(\w{3}\s+\d{1,2},?\s+\d{4})',
                r'(\d{1,2}\s+\w{3}\s+\d{4})',
            ],
            'amount': [
                r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|dollars?)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*CR',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*DR',
            ],
            'merchant': [
                r'([A-Z][A-Z0-9\s&\-\.]{3,30})',
                r'([A-Za-z0-9\s&\-\.]{3,30})\s+\d{1,2}[\/\-]\d{1,2}',
            ],
            'card_ending': [
                r'card\s+ending\s+in\s+(\d{4})',
                r'card\s+\*+(\d{4})',
                r'\*+(\d{4})',
                r'xxxx\s*(\d{4})',
            ]
        }
        
        self.statement_keywords = [
            'statement', 'billing', 'monthly', 'credit card',
            'transaction', 'purchase', 'payment', 'balance'
        ]
        
        self.payment_keywords = [
            'payment', 'due', 'minimum', 'balance', 'credit limit'
        ]
    
    def extract_transactions(self, text: str) -> List[Dict]:
        transactions = []
        
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        
        for i, line in enumerate(cleaned_lines):
            if self.is_transaction_line(line):
                transaction = self.parse_transaction_line(line, cleaned_lines, i)
                if transaction:
                    transactions.append(transaction)
        
        transactions.extend(self.extract_tabular_transactions(text))
        
        return self.deduplicate_transactions(transactions)
    
    def is_transaction_line(self, line: str) -> bool:
        has_date = any(re.search(pattern, line, re.IGNORECASE) for pattern in self.transaction_patterns['date'])
        has_amount = any(re.search(pattern, line, re.IGNORECASE) for pattern in self.transaction_patterns['amount'])
        
        return has_date and has_amount
    
    def parse_transaction_line(self, line: str, all_lines: List[str], line_index: int) -> Optional[Dict]:
        transaction = {
            'raw_text': line,
            'line_number': line_index
        }
        
        date_match = None
        for pattern in self.transaction_patterns['date']:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                date_match = match.group(1)
                break
        
        if date_match:
            parsed_date = dateparser.parse(date_match)
            if parsed_date:
                transaction['date'] = parsed_date
            else:
                transaction['date_string'] = date_match
        
        amount_match = None
        for pattern in self.transaction_patterns['amount']:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                amount_match = match.group(1)
                break
        
        if amount_match:
            try:
                amount = float(amount_match.replace(',', ''))
                transaction['amount'] = amount
            except ValueError:
                return None
        
        merchant_candidates = []
        for pattern in self.transaction_patterns['merchant']:
            matches = re.findall(pattern, line, re.IGNORECASE)
            merchant_candidates.extend(matches)
        
        if merchant_candidates:
            merchant = max(merchant_candidates, key=len).strip()
            if len(merchant) > 2:
                transaction['merchant'] = merchant
        
        description_parts = []
        words = line.split()
        for word in words:
            if (not re.match(r'^\d+[\/\-]\d+[\/\-]\d+$', word) and 
                not re.match(r'^\$?\d+[\.,]\d+$', word) and
                len(word) > 2):
                description_parts.append(word)
        
        if description_parts:
            transaction['description'] = ' '.join(description_parts[:10])
        
        if line_index > 0:
            prev_line = all_lines[line_index - 1]
            if not self.is_transaction_line(prev_line) and len(prev_line) > 10:
                transaction['additional_description'] = prev_line
        
        return transaction if 'date' in transaction and 'amount' in transaction else None
    
    def extract_tabular_transactions(self, text: str) -> List[Dict]:
        transactions = []
        
        lines = text.split('\n')
        potential_table_lines = []
        
        for line in lines:
            if self.count_numeric_fields(line) >= 2:
                potential_table_lines.append(line)
        
        if len(potential_table_lines) > 3:
            for line in potential_table_lines:
                fields = self.split_table_line(line)
                if len(fields) >= 3:
                    transaction = self.parse_table_fields(fields, line)
                    if transaction:
                        transactions.append(transaction)
        
        return transactions
    
    def count_numeric_fields(self, line: str) -> int:
        numeric_patterns = [
            r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
            r'\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
            r'\d{4}',
        ]
        
        count = 0
        for pattern in numeric_patterns:
            matches = re.findall(pattern, line)
            count += len(matches)
        
        return count
    
    def split_table_line(self, line: str) -> List[str]:
        fields = []
        
        if '\t' in line:
            fields = line.split('\t')
        elif '  ' in line:
            fields = re.split(r'\s{2,}', line)
        else:
            fields = line.split()
        
        return [field.strip() for field in fields if field.strip()]
    
    def parse_table_fields(self, fields: List[str], raw_line: str) -> Optional[Dict]:
        transaction = {
            'raw_text': raw_line,
            'table_fields': fields
        }
        
        for field in fields:
            date_parsed = dateparser.parse(field)
            if date_parsed:
                transaction['date'] = date_parsed
                break
        
        for field in fields:
            amount_match = re.search(r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', field)
            if amount_match:
                try:
                    amount = float(amount_match.group(1).replace(',', ''))
                    transaction['amount'] = amount
                    break
                except ValueError:
                    continue
        
        description_fields = []
        for field in fields:
            if (not re.match(r'^\d+[\/\-]\d+[\/\-]\d+$', field) and 
                not re.match(r'^\$?\d+[\.,]\d+$', field) and
                len(field) > 2):
                description_fields.append(field)
        
        if description_fields:
            transaction['description'] = ' '.join(description_fields[:5])
            if len(description_fields) > 0:
                transaction['merchant'] = description_fields[0]
        
        return transaction if 'date' in transaction and 'amount' in transaction else None
    
    def deduplicate_transactions(self, transactions: List[Dict]) -> List[Dict]:
        seen = set()
        unique_transactions = []
        
        for transaction in transactions:
            key = (
                transaction.get('date'),
                transaction.get('amount'),
                transaction.get('merchant', '')[:20]
            )
            
            if key not in seen:
                seen.add(key)
                unique_transactions.append(transaction)
        
        return unique_transactions
    
    def extract_credit_card_info(self, text: str) -> Dict:
        info = {}
        
        card_ending_patterns = [
            r'card\s+ending\s+in\s+(\d{4})',
            r'card\s+\*+(\d{4})',
            r'\*+(\d{4})',
            r'xxxx\s*(\d{4})',
        ]
        
        for pattern in card_ending_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['card_last_four'] = match.group(1)
                break
        
        balance_patterns = [
            r'current\s+balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'new\s+balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'balance:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in balance_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    info['current_balance'] = float(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
        
        due_date_patterns = [
            r'payment\s+due:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'due\s+date:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'due\s+on:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        ]
        
        for pattern in due_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                due_date = dateparser.parse(match.group(1))
                if due_date:
                    info['due_date'] = due_date
                    break
        
        minimum_payment_patterns = [
            r'minimum\s+payment:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'min\s+payment:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'minimum\s+due:?\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in minimum_payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    info['minimum_payment'] = float(match.group(1).replace(',', ''))
                    break
                except ValueError:
                    continue
        
        return info