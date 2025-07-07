import re
from typing import List, Dict, Optional
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

class TransactionCategorizer:
    def __init__(self):
        self.categories = {
            'Food & Dining': {
                'keywords': ['restaurant', 'food', 'dining', 'cafe', 'pizza', 'burger', 'starbucks', 'mcdonalds', 'subway', 'delivery', 'takeout', 'bar', 'pub', 'bakery', 'grocery', 'supermarket', 'market', 'whole foods', 'safeway', 'kroger'],
                'patterns': [r'.*restaurant.*', r'.*food.*', r'.*cafe.*', r'.*pizza.*'],
                'subcategories': ['Restaurants', 'Fast Food', 'Groceries', 'Coffee Shops', 'Bars & Pubs']
            },
            'Transportation': {
                'keywords': ['gas', 'fuel', 'shell', 'chevron', 'bp', 'exxon', 'mobil', 'uber', 'lyft', 'taxi', 'metro', 'bus', 'train', 'parking', 'toll', 'car', 'auto', 'repair', 'maintenance'],
                'patterns': [r'.*gas.*', r'.*fuel.*', r'.*uber.*', r'.*lyft.*'],
                'subcategories': ['Gas & Fuel', 'Ride Sharing', 'Public Transit', 'Parking', 'Auto Repair']
            },
            'Shopping': {
                'keywords': ['amazon', 'walmart', 'target', 'costco', 'best buy', 'home depot', 'lowes', 'macys', 'nordstrom', 'clothing', 'shoes', 'electronics', 'books', 'toys', 'home', 'garden'],
                'patterns': [r'.*amazon.*', r'.*walmart.*', r'.*target.*'],
                'subcategories': ['Online Shopping', 'Department Stores', 'Electronics', 'Clothing', 'Home & Garden']
            },
            'Entertainment': {
                'keywords': ['movie', 'theater', 'cinema', 'netflix', 'spotify', 'apple music', 'youtube', 'game', 'steam', 'playstation', 'xbox', 'concert', 'show', 'ticket', 'event'],
                'patterns': [r'.*movie.*', r'.*theater.*', r'.*netflix.*', r'.*spotify.*'],
                'subcategories': ['Movies', 'Streaming Services', 'Gaming', 'Concerts', 'Events']
            },
            'Health & Fitness': {
                'keywords': ['pharmacy', 'cvs', 'walgreens', 'hospital', 'doctor', 'clinic', 'medical', 'gym', 'fitness', 'yoga', 'health', 'dental', 'vision', 'prescription'],
                'patterns': [r'.*pharmacy.*', r'.*medical.*', r'.*gym.*', r'.*fitness.*'],
                'subcategories': ['Pharmacy', 'Medical', 'Fitness', 'Dental', 'Vision']
            },
            'Bills & Utilities': {
                'keywords': ['electric', 'electricity', 'water', 'gas', 'utility', 'phone', 'internet', 'cable', 'verizon', 'att', 'tmobile', 'comcast', 'xfinity', 'bill', 'payment'],
                'patterns': [r'.*electric.*', r'.*utility.*', r'.*verizon.*', r'.*comcast.*'],
                'subcategories': ['Electricity', 'Water', 'Gas', 'Internet', 'Phone']
            },
            'Travel': {
                'keywords': ['hotel', 'airline', 'flight', 'airport', 'travel', 'booking', 'expedia', 'airbnb', 'rental', 'car rental', 'hertz', 'enterprise', 'vacation'],
                'patterns': [r'.*hotel.*', r'.*airline.*', r'.*flight.*', r'.*airbnb.*'],
                'subcategories': ['Hotels', 'Flights', 'Car Rental', 'Vacation Rentals', 'Travel Booking']
            },
            'Finance': {
                'keywords': ['bank', 'atm', 'fee', 'interest', 'transfer', 'payment', 'credit', 'loan', 'mortgage', 'insurance', 'investment', 'financial'],
                'patterns': [r'.*bank.*', r'.*atm.*', r'.*fee.*', r'.*interest.*'],
                'subcategories': ['Banking Fees', 'ATM', 'Insurance', 'Loans', 'Investments']
            },
            'Education': {
                'keywords': ['school', 'university', 'college', 'tuition', 'education', 'books', 'supplies', 'course', 'class', 'learning', 'student'],
                'patterns': [r'.*school.*', r'.*university.*', r'.*education.*'],
                'subcategories': ['Tuition', 'Books', 'Supplies', 'Courses', 'Student Services']
            },
            'Personal Care': {
                'keywords': ['salon', 'spa', 'beauty', 'cosmetics', 'hair', 'nail', 'massage', 'skincare', 'personal', 'hygiene', 'grooming'],
                'patterns': [r'.*salon.*', r'.*spa.*', r'.*beauty.*'],
                'subcategories': ['Hair Care', 'Skincare', 'Spa Services', 'Cosmetics', 'Personal Hygiene']
            },
            'Other': {
                'keywords': [],
                'patterns': [],
                'subcategories': ['Miscellaneous', 'Unknown', 'Other']
            }
        }
        
        self.nlp = None
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.category_vectors = None
        self._initialize_nlp()
    
    def _initialize_nlp(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def categorize_transactions(self, transactions: List[Dict]) -> List[Dict]:
        if not transactions:
            return []
        
        for transaction in transactions:
            category, subcategory, confidence = self.categorize_single_transaction(transaction)
            transaction['category'] = category
            transaction['subcategory'] = subcategory
            transaction['confidence_score'] = confidence
        
        return transactions
    
    def categorize_single_transaction(self, transaction: Dict) -> tuple:
        text_to_analyze = self._extract_text_for_analysis(transaction)
        
        keyword_match = self._keyword_matching(text_to_analyze)
        if keyword_match[2] > 0.8:
            return keyword_match
        
        pattern_match = self._pattern_matching(text_to_analyze)
        if pattern_match[2] > 0.7:
            return pattern_match
        
        if self.nlp:
            nlp_match = self._nlp_matching(text_to_analyze)
            if nlp_match[2] > 0.6:
                return nlp_match
        
        ml_match = self._ml_matching(text_to_analyze)
        if ml_match[2] > 0.5:
            return ml_match
        
        return 'Other', 'Miscellaneous', 0.3
    
    def _extract_text_for_analysis(self, transaction: Dict) -> str:
        text_parts = []
        
        if 'merchant' in transaction:
            text_parts.append(transaction['merchant'])
        
        if 'description' in transaction:
            text_parts.append(transaction['description'])
        
        if 'raw_text' in transaction:
            text_parts.append(transaction['raw_text'])
        
        return ' '.join(text_parts).lower()
    
    def _keyword_matching(self, text: str) -> tuple:
        best_match = ('Other', 'Miscellaneous', 0.0)
        
        for category, data in self.categories.items():
            keywords = data['keywords']
            matches = sum(1 for keyword in keywords if keyword in text)
            
            if matches > 0:
                confidence = min(matches / len(keywords), 1.0)
                if confidence > best_match[2]:
                    subcategory = data['subcategories'][0] if data['subcategories'] else 'General'
                    best_match = (category, subcategory, confidence)
        
        return best_match
    
    def _pattern_matching(self, text: str) -> tuple:
        best_match = ('Other', 'Miscellaneous', 0.0)
        
        for category, data in self.categories.items():
            patterns = data['patterns']
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    subcategory = data['subcategories'][0] if data['subcategories'] else 'General'
                    return (category, subcategory, 0.85)
        
        return best_match
    
    def _nlp_matching(self, text: str) -> tuple:
        if not self.nlp:
            return ('Other', 'Miscellaneous', 0.0)
        
        doc = self.nlp(text)
        entities = [ent.text.lower() for ent in doc.ents]
        
        for category, data in self.categories.items():
            keywords = data['keywords']
            entity_matches = sum(1 for entity in entities if any(keyword in entity for keyword in keywords))
            
            if entity_matches > 0:
                confidence = min(entity_matches / max(len(entities), 1), 0.9)
                if confidence > 0.4:
                    subcategory = data['subcategories'][0] if data['subcategories'] else 'General'
                    return (category, subcategory, confidence)
        
        return ('Other', 'Miscellaneous', 0.0)
    
    def _ml_matching(self, text: str) -> tuple:
        try:
            category_texts = []
            category_names = []
            
            for category, data in self.categories.items():
                if category != 'Other':
                    category_text = ' '.join(data['keywords'])
                    category_texts.append(category_text)
                    category_names.append(category)
            
            if not category_texts:
                return ('Other', 'Miscellaneous', 0.0)
            
            all_texts = category_texts + [text]
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)
            
            text_vector = tfidf_matrix[-1]
            category_vectors = tfidf_matrix[:-1]
            
            similarities = cosine_similarity(text_vector, category_vectors).flatten()
            
            best_idx = similarities.argmax()
            best_similarity = similarities[best_idx]
            
            if best_similarity > 0.3:
                best_category = category_names[best_idx]
                subcategory = self.categories[best_category]['subcategories'][0]
                return (best_category, subcategory, best_similarity)
        
        except Exception as e:
            print(f"ML matching error: {e}")
        
        return ('Other', 'Miscellaneous', 0.0)
    
    def add_custom_rule(self, pattern: str, category: str, subcategory: str, confidence: float = 0.9):
        if category not in self.categories:
            self.categories[category] = {
                'keywords': [],
                'patterns': [],
                'subcategories': [subcategory]
            }
        
        self.categories[category]['patterns'].append(pattern)
        if subcategory not in self.categories[category]['subcategories']:
            self.categories[category]['subcategories'].append(subcategory)
    
    def get_category_statistics(self, transactions: List[Dict]) -> Dict:
        stats = {}
        
        for transaction in transactions:
            category = transaction.get('category', 'Other')
            amount = transaction.get('amount', 0)
            
            if category not in stats:
                stats[category] = {
                    'count': 0,
                    'total_amount': 0,
                    'avg_amount': 0,
                    'transactions': []
                }
            
            stats[category]['count'] += 1
            stats[category]['total_amount'] += amount
            stats[category]['transactions'].append(transaction)
        
        for category, data in stats.items():
            if data['count'] > 0:
                data['avg_amount'] = data['total_amount'] / data['count']
        
        return stats
    
    def detect_recurring_transactions(self, transactions: List[Dict]) -> List[Dict]:
        recurring = []
        
        sorted_transactions = sorted(transactions, key=lambda x: x.get('date', ''))
        
        merchant_groups = {}
        for transaction in sorted_transactions:
            merchant = transaction.get('merchant', 'Unknown')
            if merchant not in merchant_groups:
                merchant_groups[merchant] = []
            merchant_groups[merchant].append(transaction)
        
        for merchant, merchant_transactions in merchant_groups.items():
            if len(merchant_transactions) >= 3:
                amounts = [t.get('amount', 0) for t in merchant_transactions]
                avg_amount = sum(amounts) / len(amounts)
                amount_variance = sum((x - avg_amount) ** 2 for x in amounts) / len(amounts)
                
                if amount_variance < (avg_amount * 0.1) ** 2:
                    for transaction in merchant_transactions:
                        transaction['is_recurring'] = True
                    recurring.extend(merchant_transactions)
        
        return recurring