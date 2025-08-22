from src.models.user import db
from datetime import datetime, timedelta
import random
import string

class Key(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_value = db.Column(db.String(8), unique=True, nullable=False)
    hwid = db.Column(db.String(255), nullable=True)  # HWID vinculado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    first_use_at = db.Column(db.DateTime, nullable=True)  # Quando foi usado pela primeira vez
    expires_in_days = db.Column(db.Integer, nullable=True)  # Dias de expiração
    expires_in_hours = db.Column(db.Integer, nullable=True)  # Horas de expiração
    is_active = db.Column(db.Boolean, default=True)  # Se a chave está ativa
    is_paused = db.Column(db.Boolean, default=False)  # Se a chave está pausada
    pause_count = db.Column(db.Integer, default=0)  # Quantas vezes foi pausada (máx 3)
    hwid_reset_count = db.Column(db.Integer, default=0)  # Quantas vezes o HWID foi resetado (máx 2)
    
    def __repr__(self):
        return f'<Key {self.key_value}>'
    
    @staticmethod
    def generate_key():
        """Gera uma chave única de 8 dígitos"""
        while True:
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Key.query.filter_by(key_value=key).first():
                return key
    
    def is_expired(self):
        """Verifica se a chave está expirada"""
        if not self.first_use_at:
            return False  # Não expirou se nunca foi usada
        
        if self.expires_in_days:
            expiry_date = self.first_use_at + timedelta(days=self.expires_in_days)
        elif self.expires_in_hours:
            expiry_date = self.first_use_at + timedelta(hours=self.expires_in_hours)
        else:
            return False  # Sem expiração definida
        
        return datetime.utcnow() > expiry_date
    
    def get_remaining_time(self):
        """Retorna o tempo restante da chave"""
        if not self.first_use_at:
            if self.expires_in_days:
                return f"{self.expires_in_days} dias (não utilizada)"
            elif self.expires_in_hours:
                return f"{self.expires_in_hours} horas (não utilizada)"
            return "Sem expiração"
        
        if self.expires_in_days:
            expiry_date = self.first_use_at + timedelta(days=self.expires_in_days)
        elif self.expires_in_hours:
            expiry_date = self.first_use_at + timedelta(hours=self.expires_in_hours)
        else:
            return "Sem expiração"
        
        remaining = expiry_date - datetime.utcnow()
        if remaining.total_seconds() <= 0:
            return "Expirada"
        
        days = remaining.days
        hours = remaining.seconds // 3600
        
        if days > 0:
            return f"{days} dias e {hours} horas"
        else:
            return f"{hours} horas"
    
    def can_pause(self):
        """Verifica se a chave pode ser pausada"""
        return self.pause_count < 3
    
    def can_reset_hwid(self):
        """Verifica se o HWID pode ser resetado"""
        return self.hwid_reset_count < 2
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key_value,
            'hwid': self.hwid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'first_use_at': self.first_use_at.isoformat() if self.first_use_at else None,
            'expires_in_days': self.expires_in_days,
            'expires_in_hours': self.expires_in_hours,
            'is_active': self.is_active,
            'is_paused': self.is_paused,
            'is_expired': self.is_expired(),
            'remaining_time': self.get_remaining_time(),
            'pause_count': self.pause_count,
            'hwid_reset_count': self.hwid_reset_count,
            'can_pause': self.can_pause(),
            'can_reset_hwid': self.can_reset_hwid()
        }

