# Google OAuth Setup für Todo-App

## 1. Google Cloud Console Setup

### Schritt 1: Google Cloud Projekt erstellen
1. Gehen Sie zu: https://console.cloud.google.com/
2. Neues Projekt erstellen: "Todo-App"
3. Projekt auswählen

### Schritt 2: OAuth 2.0 Credentials erstellen
1. APIs & Services → Credentials
2. "Create Credentials" → "OAuth 2.0 Client IDs"
3. Application type: "Web application"
4. Name: "Todo App OAuth"

### Schritt 3: Authorized redirect URIs
**Für Entwicklung:**
- http://localhost:5000/auth/callback
- http://127.0.0.1:5000/auth/callback

**Für Produktion:**
- http://your-domain.com/auth/callback
- https://your-domain.com/auth/callback

### Schritt 4: Client ID und Secret notieren
- Client ID: wird in der App benötigt
- Client Secret: wird in der App benötigt

## 2. Erforderliche Scopes
- openid
- email
- profile

## 3. Environment Variablen
```
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
```
