# UTeM SOC Phishing Detection System

## Overview
A real-time WhatsApp monitoring system that uses Machine Learning to detect phishing threats. The system integrates a FastAPI-based dashboard with a Selenium-driven WhatsApp Web scraper.

## Features
- **Real-time Monitoring**: Scrapes incoming WhatsApp messages using Selenium.
- **Phishing Detection**: Employs a hybrid Machine Learning model (Random Forest & SVM) to analyze message risk.
- **Interactive Dashboard**: View live message feeds and system status via WebSockets.
- **Automated Warnings**: Automatically sends anti-scam warnings to the chat when high-risk threats are detected.

## Tech Stack
- **Backend**: FastAPI
- **Automation**: Selenium (Chrome)
- **Machine Learning**: Scikit-learn, Pandas
- **Frontend**: HTML/JS (Static Assets)

## Installation

### Prerequisites
- Python 3.10+
- Google Chrome installed

### Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application
To start the FastAPI server:
```bash
python coding/app.py
```
Then navigate to `http://127.0.0.1:8000` in your browser.

## Project Structure
- `coding/app/`: FastAPI application (routes, models, services).
- `coding/radar.py`: Selenium worker for WhatsApp monitoring.
- `coding/learning_engine.py`: ML pipeline and model training logic.
- `coding/whatsapp_dataset.csv`: Dataset used for training.
- `coding/static/` & `coding/templates/`: UI assets.
