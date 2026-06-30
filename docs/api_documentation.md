# API Documentation

## AI-Powered Code Review & Bug Detection System

Base URL: `http://localhost:5000`

---

## Endpoints

### 1. GET /
Home page

### 2. GET /review
Code review page

### 3. GET /dashboard
Dashboard page

### 4. POST /analyze
Analyze code from text input

**Request:**
```json
{
  "code": "def hello():\n    print('world')",
  "filename": "test.py"
}