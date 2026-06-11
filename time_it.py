import time
from functools import wraps


def time_it(func):
    import time

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end - start:.4f} seconds")
        return result

    return wrapper


print("Please enter customer details to place the order: ")
name = input("Client Name: ")
email = f"{name}.gmail.com"
product_id = input("Product ID: ")
quantity = int(input("Quantity: "))
price = float(input("Price: "))

@time_it
def create_order(name, email, product_id, quantity, price):
    time.sleep(2)
    total_price = price * quantity
    print("Order placed successfully")
    print("Name: {}".format(name))
    print("Email: {}".format(email))
    print("Product ID: {}".format(product_id))
    print("Quantity: {}".format(quantity))
    print("Total Price: {}".format(total_price))

print(create_order.__name__)
create_order(name=name, email=email, product_id=product_id, quantity=quantity, price=price)
