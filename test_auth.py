from passlib.context import CryptContext
ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
sha256_pw = "437996709cdcc6223af620720f7652503ea225707143499ea5d3485508bc45d1"
db_hash = "$2b$12$F.zeAdphXOZf0DUHzBBHX.VqDzaajW9.iCdQl5xkDtLEBVfl9TNSC"
print("verify:", ctx.verify(sha256_pw, db_hash))
