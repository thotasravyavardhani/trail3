# QuMail Secure Email Client

## Overview
QuMail is a quantum-secure email client with end-to-end encryption featuring:
- FastAPI Python backend with quantum cryptography (PQC)
- React TypeScript frontend with Tailwind CSS
- SQLite database with SQLAlchemy ORM
- Mock Key Manager for quantum key distribution
- Email service supporting IMAP/SMTP

## Project Architecture
### Backend (Port 8000)
- **Location**: `/backend/`
- **Tech Stack**: FastAPI, SQLAlchemy, SQLite, Cryptography
- **Main Entry**: `main.py` 
- **Features**: Authentication, email encryption/decryption, IMAP/SMTP integration

### Frontend (Port 5000) 
- **Location**: `/frontend/`
- **Tech Stack**: React 18, TypeScript, Tailwind CSS
- **Build Tool**: react-scripts
- **Features**: Login, inbox, compose, settings UI

## Recent Changes (Sept 18, 2025)
- Configured for Replit environment
- Fixed Tailwind CSS PostCSS configuration 
- Set up dual workflows for frontend/backend
- Configured CORS for Replit proxy support
- Set deployment target as VM for stateful app

## Development Setup
- Backend runs on `localhost:8000`
- Frontend runs on `0.0.0.0:5000` with proxy to backend
- SQLite database: `backend/qumail.db`
- Logs: Backend uses structured JSON logging

## Deployment Configuration
- Target: VM (maintains backend state)
- Build: Frontend React build process
- Run: Concurrent backend Python + frontend static serve

## User Preferences
- Security-focused email application
- Quantum-secure cryptography emphasis
- Professional email client interface