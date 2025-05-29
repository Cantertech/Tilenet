# # urls.py in your Django app (e.g., 'estimates')

# from django.urls import path, include
# from . import views # Import your views

# urlpatterns = [
#     # --- Estimate URLs ---
#     # List all estimates for the user or create a new estimate
#     path('estimates/', views.EstimateListCreateView.as_view(), name='estimate-list-create'),
#     # Retrieve, update, or delete a specific estimate by ID
#     path('estimates/<int:pk>/', views.EstimateDetailView.as_view(), name='estimate-detail'),

#     # --- Customer URLs (Optional) ---
#     # List all customers for the user or create a new customer
#     path('customers/', views.CustomerListCreateView.as_view(), name='customer-list-create'),
#     # Retrieve, update, or delete a specific customer by ID
#     path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer-detail'),

#     # --- Nested URLs for Estimate Items (Optional) ---
#     # You can define URLs for the related items if you need to manage them
#     # independently of the main estimate endpoint (e.g., adding a single material item).
#     # The main EstimateDetailView with nested serializers already handles
#     # creating/updating/deleting all items when the parent estimate is updated.

#     # Example: URLs for MaterialItems nested under an Estimate
#     path('estimates/<int:estimate_id>/materials/', views.MaterialItemListCreateView.as_view(), name='materialitem-list-create'),
#     # path('materials/<int:pk>/', views.MaterialItemDetailView.as_view(), name='materialitem-detail'), # If you need detail view for individual item

#     # Add similar paths for RoomAreas and LabourItems if necessary
#     # path('estimates/<int:estimate_id>/rooms/', views.RoomAreaItemListCreateView.as_view(), name='roomarea-list-create'),
#     # path('estimates/<int:estimate_id>/labour/', views.LabourItemListCreateView.as_view(), name='labouritem-list-create'),


# ]

# your_project/estimates/urls.py
from django.urls import path, include
from .views import (
    EstimateListCreateView, # For GET (list) and POST (create) /estimates/
    EstimateDetailView,    # For GET (detail), PUT/PATCH (update), DELETE (delete) /estimates/{pk}/
    UserCustomerListView,  # For GET (list) /customers/ (for contact page)

    # --- Optional Views (Uncomment if you need standalone CRUD for these) ---
    CustomerListCreateView, # For GET (list all user's customers), POST (create) standalone customers
    # CustomerDetailView,    # For GET, PUT/PATCH, DELETE specific standalone customer

    # --- Optional Nested Item Views (Uncomment if you need separate endpoints for these) ---
    # MaterialItemListCreateView, # For GET (list materials for estimate), POST (create material for estimate)
    # RoomAreaItemListCreateView, # For GET (list rooms for estimate), POST (create room for estimate)
    # LabourItemListCreateView, # For GET (list labour for estimate), POST (create labour for estimate)
)

# Define the URL patterns for the estimates app
urlpatterns = [
    # Endpoint for listing and creating Estimates (Projects) for the authenticated user.
    # GET /estimates/ -> Lists all Estimates for the user.
    # POST /estimates/ -> Creates a new Estimate for the user and generates PDF.
    path('estimates/', EstimateListCreateView.as_view(), name='estimate-list-create'),

    # Endpoint for retrieving, updating, and deleting a specific Estimate (Project) by its owner.
    # GET /estimates/{pk}/ -> Retrieves details for a specific Estimate.
    # PUT /estimates/{pk}/ -> Updates a specific Estimate and regenerates PDF.
    # PATCH /estimates/{pk}/ -> Partially updates a specific Estimate and regenerates PDF.
    # DELETE /estimates/{pk}/ -> Deletes a specific Estimate.
    path('estimates/<int:pk>/', EstimateDetailView.as_view(), name='estimate-detail'),

    # Endpoint for listing all Customers associated with the authenticated user's Estimates.
    # This is intended for the 'contact page' list.
    # GET /customers/ -> Lists customers (id, name, location, phone) linked to user's estimates.
    path('customers/', UserCustomerListView.as_view(), name='user-customer-list'),


    # --- Optional Standalone Customer Management URLs ---
    # Uncomment these if you need separate endpoints for full CRUD operations on Customer objects,
    # separate from their association with Estimates.
    # path('all-customers/', CustomerListCreateView.as_view(), name='customer-list-create'), # Example path
    # path('all-customers/<int:pk>/', CustomerDetailView.as_view(), name='customer-detail'), # Example path

    # --- Optional Nested Item Management URLs ---
    # Uncomment these if you need separate endpoints to manage MaterialItems, RoomAreas, or LabourItems
    # linked to a specific Estimate. Remember to also define their respective Detail/Update/Delete views
    # if you need more than just list/create via these endpoints.
    # path('estimates/<int:estimate_id>/materials/', MaterialItemListCreateView.as_view(), name='materialitem-list-create'),
    # path('estimates/<int:estimate_id>/rooms/', RoomAreaItemListCreateView.as_view(), name='roomarea-list-create'),
    # path('estimates/<int:estimate_id>/labour/', LabourItemListCreateView.as_view(), name='labouritem-list-create'),
    # # Example detail view for a nested item (requires MaterialItemDetailView in views.py)
    # # path('estimates/<int:estimate_id>/materials/<int:pk>/', MaterialItemDetailView.as_view(), name='materialitem-detail'),

]
