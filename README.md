Overview:
This backend implements a scalable and testable Campaign Discount Service, enabling business owners to manage discount strategies efficiently.

Features:

1. Campaign CRUD

Full REST API with Create, Read, Update, Delete.

2. Available Campaigns API

Determines which campaigns apply to a customer’s cart.

Supports:

GET (/api/campaigns/available/)

POST (/api/campaigns/available/)

3. Redeem Discount

Applies discount with all business rules enforced.

4. Target Customers

Campaigns can target:

All customers

OR selected customers

5. Swagger Documentation

Available at:
  /api/docs/

6. Automated Tests

Unit tests

Integration tests



API Endpoints
Campaign CRUD
GET     /api/campaigns/
POST    /api/campaigns/
GET     /api/campaigns/{id}/
PATCH   /api/campaigns/{id}/
PUT     /api/campaigns/{id}/
DELETE  /api/campaigns/{id}/


Available Campaigns (GET)
/api/campaigns/available/?customer_id=1&subtotal=1200&delivery=80

Available Campaigns (POST)
{
  "customer_id": 1,
  "subtotal": "1200.00",
  "delivery": "80.00"
}


Redeem Discount
POST /api/campaigns/redeem/


1. Clone Repository
git clone <https://github.com/ashishchaurasiyaa/Campaign-Management.git>
cd discount_platform

python3 -m venv .venv
source .venv/bin/activate


pip install -r requirements.txt


python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

python manage.py seed_sample --fresh

python manage.py test campaigns



