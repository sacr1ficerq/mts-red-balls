# NLP Tricks for Kaggle Competitions

## Text Preprocessing

### Basic Cleaning
```python
import re
import string

def clean_text(text):
    text = text.lower()
    text = re.sub(r'http\S+|www\S+', '', text)  # Remove URLs
    text = re.sub(r'<.*?>', '', text)  # Remove HTML tags
    text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text
```

### Tokenization
- Word tokenization: `nltk.word_tokenize()` or `text.split()`.
- Subword tokenization: BPE (used in BERT, GPT). Handles OOV words.
- Character tokenization: For noisy text, typos.

### Stopword Removal
```python
from nltk.corpus import stopwords
stop_words = set(stopwords.words('english'))
tokens = [w for w in tokens if w not in stop_words]
```
- Note: For transformer models, don't remove stopwords — they handle it internally.

### Stemming and Lemmatization
```python
from nltk.stem import PorterStemmer, WordNetLemmatizer
stemmer = PorterStemmer()
lemmatizer = WordNetLemmatizer()
stemmed = [stemmer.stem(w) for w in tokens]
lemmatized = [lemmatizer.lemmatize(w) for w in tokens]
```

## Classical NLP Features

### TF-IDF
```python
from sklearn.feature_extraction.text import TfidfVectorizer
tfidf = TfidfVectorizer(
    max_features=50000,
    ngram_range=(1, 2),  # Unigrams and bigrams
    min_df=2,  # Ignore terms appearing in < 2 docs
    max_df=0.95,  # Ignore terms in > 95% of docs
    sublinear_tf=True  # Apply log normalization to TF
)
X_tfidf = tfidf.fit_transform(texts)
```

### Count Vectorizer
```python
from sklearn.feature_extraction.text import CountVectorizer
cv = CountVectorizer(max_features=10000, ngram_range=(1, 3))
X_counts = cv.fit_transform(texts)
```

### Text Statistics Features
```python
def text_features(text):
    return {
        'length': len(text),
        'word_count': len(text.split()),
        'unique_words': len(set(text.split())),
        'avg_word_length': np.mean([len(w) for w in text.split()]),
        'capital_ratio': sum(1 for c in text if c.isupper()) / max(len(text), 1),
        'punctuation_count': sum(1 for c in text if c in string.punctuation),
        'digit_ratio': sum(1 for c in text if c.isdigit()) / max(len(text), 1),
        'exclamation_count': text.count('!'),
        'question_count': text.count('?'),
    }
```

## Transformer Models (State of the Art)

### BERT Fine-tuning
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = 'bert-base-uncased'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

# Tokenize
inputs = tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')

# Training with AdamW
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
```

### Best Models by Task
- **Text Classification**: DeBERTa-v3, RoBERTa, BERT.
- **NER**: DeBERTa, BERT-CRF.
- **Question Answering**: DeBERTa-v3, ELECTRA.
- **Text Generation**: GPT-2, T5, BART.
- **Multilingual**: XLM-RoBERTa, mBERT.
- **Sentence Similarity**: sentence-transformers (all-MiniLM-L6-v2, all-mpnet-base-v2).

### Efficient Fine-tuning
- **LoRA**: Low-Rank Adaptation. Fine-tune only small matrices. Use `peft` library.
- **Adapter layers**: Insert small trainable layers. Less parameters than full fine-tuning.
- **Prompt tuning**: Learn soft prompts instead of fine-tuning weights.

### Sentence Embeddings
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)
# embeddings shape: (n_texts, 384)
```

## NLP Competition Strategies

### Ensemble of Transformers
- Fine-tune multiple architectures: BERT + RoBERTa + DeBERTa.
- Use different random seeds.
- Average predictions or stack with logistic regression.

### Data Augmentation
- **Back-translation**: Translate to another language and back.
- **Synonym replacement**: Replace words with synonyms (WordNet).
- **Random insertion/deletion/swap**: Randomly modify tokens.
- **EDA (Easy Data Augmentation)**: Combines above techniques.
- **Paraphrase generation**: Use T5 or GPT to paraphrase.

### Pseudo-Labeling for NLP
1. Fine-tune on labeled data.
2. Predict on unlabeled/test data.
3. Add high-confidence predictions to training set.
4. Retrain.

### Multi-Task Learning
- If multiple related tasks available, train jointly.
- Shared encoder, task-specific heads.
- Often improves performance on all tasks.

### Knowledge Distillation
- Train large teacher model.
- Train small student model to mimic teacher's soft predictions.
- Student is faster at inference.

## Handling Long Documents
- **Truncation**: Simple but loses information.
- **Sliding window**: Process overlapping chunks, aggregate predictions.
- **Hierarchical models**: Sentence-level then document-level.
- **Longformer / BigBird**: Transformers with efficient attention for long sequences.

## Text Similarity Tasks
```python
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer('all-mpnet-base-v2')

# Compute cosine similarity
emb1 = model.encode(texts1, convert_to_tensor=True)
emb2 = model.encode(texts2, convert_to_tensor=True)
cosine_scores = util.cos_sim(emb1, emb2)
```

## Named Entity Recognition (NER)
```python
import spacy
nlp = spacy.load('en_core_web_sm')
doc = nlp(text)
entities = [(ent.text, ent.label_) for ent in doc.ents]
# Labels: PERSON, ORG, GPE, DATE, MONEY, etc.
```

## Practical Tips
- Always check class distribution in NLP tasks — often imbalanced.
- Use `max_length=128` for sentence classification (faster), `512` for document.
- Gradient accumulation for large batch sizes on limited GPU memory.
- Mixed precision training (`fp16=True`) for 2x speedup.
- Freeze lower layers initially, then unfreeze for fine-tuning.
