"""
配置管理器 - 使用 AES 加密存储敏感配置
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ConfigManager:
    """加密配置管理器"""
    
    def __init__(self, config_file: str = "data/config.enc"):
        """初始化配置管理器"""
        self.config_file = config_file
        # 硬编码的盐和密码用于基本混淆
        self._salt = b'article_generator_salt_2025'
        self._password = b'article_generator_secret_key'
        self._key = self._generate_key()
        self._fernet = Fernet(self._key)
    
    def _generate_key(self) -> bytes:
        """生成加密密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self._password))
    
    def save_config(self, config: dict) -> bool:
        """保存配置到加密文件"""
        try:
            json_data = json.dumps(config)
            encrypted_data = self._fernet.encrypt(json_data.encode())
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def load_config(self) -> dict:
        """从加密文件加载配置"""
        if not os.path.exists(self.config_file):
            return {}
        
        try:
            with open(self.config_file, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            print(f"加载配置失败: {e}")
            return {}
    
    def get(self, key: str, default=None):
        """获取配置值"""
        config = self.load_config()
        return config.get(key, default)
    
    def set(self, key: str, value):
        """设置配置值"""
        config = self.load_config()
        config[key] = value
        self.save_config(config)
