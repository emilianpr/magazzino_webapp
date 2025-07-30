from werkzeug.security import generate_password_hash, check_password_hash

password = "Emilian@21082007"

hash = generate_password_hash(password)

print (hash)