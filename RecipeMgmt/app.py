import datetime
import os
import random
import re
from datetime import date, datetime, timedelta

import pymongo
from bson import ObjectId
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from others import (start_session, login_required,
                    admin_only, user_only, parse_json, RecipeStatus)
import db


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = APP_ROOT + "/static"

app = Flask(__name__)
app.secret_key = "plokmnjiuhbvgytfcxdreszaqw"


# admin Views
@app.route("/admin/")
@app.route("/admin/login/", methods=['GET', 'POST'])
def admin_login():
    error_msg = ""
    if request.method == "POST":
        values = {
            "user_name": request.form.get("user_name"),
            "password": request.form.get("password"),
        }

        result = db.admin.find_one(values)
        if result:
            start_session(result)
            session["is_admin"] = True

            return redirect(url_for("admin_home"))
        else:
            error_msg = "Invalid Login Credentials"

    return render_template("/admin/login.html", error_msg=error_msg)


@app.route("/admin/home/")
@login_required
@admin_only
def admin_home():

    total_recipes_count = db.recipes.count_documents({})
    recipes_pending_approval_count = db.recipes.count_documents(
        {"status": RecipeStatus.Pending.value})
    recipes_approved_count = db.recipes.count_documents(
        {"status": RecipeStatus.Approved.value})
    recipes_rejected_count = db.recipes.count_documents(
        {"status": RecipeStatus.Rejected.value})
    registered_users = db.users.count_documents({})

    dashboard = {
        "recipes": total_recipes_count,
        "pending": recipes_pending_approval_count,
        "approved": recipes_approved_count,
        "rejected": recipes_rejected_count,
        "registered_users": registered_users
    }

    admin_id = session["user"]["_id"]["$oid"]

    # recipes uploaded by user pending for approvale
    recipes = db.recipes.aggregate([
        {"$match": {"inserted_by": {"$ne": ObjectId(
            admin_id)}, "status": RecipeStatus.Pending.value}},
        {
            "$lookup": {
                "from": db.users.name,
                "localField": "inserted_by",
                "foreignField": "_id",
                "as": "user"
            }
        }
    ])
    return render_template("/admin/home.html", recipes=recipes, dashboard=dashboard)

# admin - change password


@app.route("/admin/change-password/", methods=['GET', 'POST'])
def admin_change_password():
    if request.method == "POST":
        values = {
            "password": request.form.get("password"),
        }
        db.admin.update_one({}, {"$set": values})
        flash("Password Updated successfully", "success")
        return redirect(url_for("admin_change_password"))

    return render_template("/admin/change-password.html")


@app.route("/admin/categories/")
@login_required
@admin_only
def admin_categories():
    category = ""
    category_id = request.args.get("category_id")
    # Edit Categories
    if category_id:
        category = db.categories.find_one({"_id": ObjectId(category_id)})

    # get all categories with status true
    categories = db.categories.find({"is_active": True})
    categories = list(categories)
    list.reverse(categories)

    return render_template("/admin/categories.html", category=category, categories=categories)


@app.route("/admin/categories/", methods=['POST'])
def admin_categories_post():
    category_name = request.form.get("category_name")
    category_id = request.form.get("category_id")
    cat_image = request.files.get('category_image')
    if not category_id:
        # Add Category
        db.categories.insert_one(
            {"category_name": category_name, "img_file_name": cat_image.filename, "is_active": True})
        cat_image.save(APP_ROOT+"/images/categories/"+cat_image.filename)
        flash("Category Added Successfully", "success")
    else:
        # Update Category
        image_filename = request.form.get('img_file_name')
        if cat_image.filename != "":
            image_filename = cat_image.filename

        db.categories.update_one({"_id": ObjectId(category_id)}, {
                                 "$set": {"category_name": category_name, "img_file_name": image_filename, }})

        # move image to folder
        if cat_image.filename != "":
            cat_image.save(APP_ROOT+"/images/categories/"+cat_image.filename)

        flash("Category Updates Successfully", "success")

    return redirect(url_for("admin_categories"))

# admin - delete category
@app.route("/admin/delete-category/<cid>/")
def admin_delete_category(cid):
    category_id = ObjectId(cid)
    # get all sub_categories associated with this category
    sub_categories = db.sub_categories.find({"category_id":category_id})
    if sub_categories:
        for scat in sub_categories:
            # delete all recipes associated with this sub category
            db.recipes.delete_many({"sub_category_id":ObjectId(scat['_id'])})

        # delete all sub categories associated with this category
        db.sub_categories.delete_many({"category_id":category_id})

    # delete this category
    db.categories.delete_one({"_id":category_id})
    flash("Category deleted successfully", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/sub-categories/")
@login_required
@admin_only
def admin_sub_categories():
    sub_category = ""
    sub_category_id = request.args.get("sub_id")
    # Edit Categories
    if sub_category_id:
        sub_category = db.sub_categories.find_one(
            {"_id": ObjectId(sub_category_id)})

    categories = db.categories.find({"is_active": True})

    sub_category_list = db.sub_categories.aggregate([
        {"$match": {"is_active": True}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }
        }
    ])

    return render_template("admin/sub-categories.html", categories=categories, sub_category=sub_category, sub_category_list=sub_category_list)


@app.route("/admin/sub-categories/", methods=['POST'])
def admin_sub_categories_post():

    sub_category_id = request.form.get("sub_category_id")
    category_id = request.form.get("category_id")
    sub_category_name = request.form.get("sub_category_name")
    image = request.files.get('sub_category_image')

    if not sub_category_id:
        # Add Sub Category
        db.sub_categories.insert_one({"category_id": ObjectId(
            category_id), "sub_category_name": sub_category_name, "img_file_name": image.filename, "is_active": True})

        image.save(APP_ROOT+"/images/sub_categories/"+image.filename)

        flash("Sub category Added Successfully", "success")
    else:
        # Update Sub Category
        image_filename = request.form.get('img_file_name')
        if image.filename != "":
            print("Indie")
            image_filename = image.filename

        print(image_filename)
        db.sub_categories.update_one({"_id": ObjectId(sub_category_id)}, {"$set": {"category_id": ObjectId(
            category_id), "sub_category_name": sub_category_name, "img_file_name": image_filename}})

        # move image to folder
        if image.filename != "":
            image.save(APP_ROOT+"/images/sub_categories/"+image.filename)

        flash("Sub category Updates Successfully", "success")

    return redirect(url_for("admin_sub_categories"))

# admin - delete sub category
@app.route("/admin/delete-sub-category/<scid>/")
def admin_delete_sub_category(scid):
    sub_category_id = ObjectId(scid)
    
    # delete all recipes associated with this sub category
    db.recipes.delete_many({"sub_category_id":sub_category_id})

    # delete this sub category
    db.sub_categories.delete_one({"_id":sub_category_id})
    
    flash("Sub Category deleted successfully", "success")
    return redirect(url_for("admin_sub_categories"))


# admin recipes
@app.route("/admin/recipes/")
@login_required
@admin_only
def admin_recipes():
    admin_id = session['user']['_id']['$oid']
    recipes = db.recipes.aggregate([
        {"$match": {"inserted_by": ObjectId(admin_id), "is_active": True}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }
        },
        {
            "$lookup": {
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "as": "sub_category"
            }
        }
    ])
    recipes = list(recipes)
    list.reverse(recipes)
    return render_template("/admin/recipes.html", recipes=recipes)



# admin view recipe
@app.route("/admin/view-recipe/<recipe_id>/")
@login_required
@admin_only
def admin_view_recipe(recipe_id):
    recipe = db.recipes.aggregate([
        {"$match": {"_id": ObjectId(recipe_id), "is_active": True}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }
        },
        {
            "$lookup": {
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "as": "sub_category"
            }
        },
        {
            "$lookup": {
                "from": db.reviews.name,
                "localField": "_id",
                "foreignField": "recipe_id",
                "as": "reviews"
            }
        }
    ])
    recipe = list(recipe)
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/admin/recipe-view.html", recipe=recipe[0])


@app.route("/admin/add-recipe/", methods=['GET', 'POST'])
@login_required
@admin_only
def admin_add_recipe():
    admin_id = session['user']['_id']['$oid']

    if request.method == "POST":
        image = request.files.get('recipe_image')
        values = {
            "category_id": ObjectId(request.form.get("category_id")),
            "sub_category_id": ObjectId(request.form.get("sub_category_id")),
            "recipe_title": request.form.get("recipe_title"),
            "servings": request.form.get("servings"),
            "cook_time": request.form.get("cook_time"),
            "description": request.form.get("description"),
            "ingredients": [],
            "directions": [],
            "nutritional_information": [],
            "img_file_name": image.filename,
            "inserted_by": ObjectId(admin_id),
            "is_active": True,
            "status": RecipeStatus.Approved.value
        }
        db.recipes.insert_one(values)
        image.save(APP_ROOT+"/images/recipes/"+image.filename)
        flash("Recipe Added Successfully", "success")
        return redirect(url_for("admin_recipes"))

    recipe = ""
    categories = db.categories.find({"is_active": True})
    sub_categories = db.sub_categories.find({"is_active": True})
    return render_template("/admin/recipe-save.html", recipe=recipe, categories=categories, sub_categories=sub_categories)

# recipe - edit


@app.route("/admin/edit-recipe/<recipe_id>/",  methods=['GET', 'POST'])
def admin_edit_recipe(recipe_id):

    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        image = request.files.get('recipe_image')
        image_filename = request.form.get('img_file_name')

        if image.filename != "":
            image_filename = image.filename

        values = {
            "category_id": ObjectId(request.form.get("category_id")),
            "sub_category_id": ObjectId(request.form.get("sub_category_id")),
            "recipe_title": request.form.get("recipe_title"),
            "servings": request.form.get("servings"),
            "cook_time": request.form.get("cook_time"),
            "description": request.form.get("description"),
            "img_file_name": image_filename
        }

        db.recipes.update_one({"_id": ObjectId(recipe_id)}, {"$set": values})
        # Save recipe image if uploaded
        if image.filename != "":
            image.save(APP_ROOT+"/images/recipes/"+image.filename)

        flash("Recipe Updated Successfully", "success")
        return redirect(url_for("admin_recipes"))

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    categories = db.categories.find({"is_active": True})
    sub_categories = db.sub_categories.find({"is_active": True})
    return render_template("/admin/recipe-save.html", recipe=recipe, categories=categories, sub_categories=sub_categories)

# admin - ingredients
@app.route("/admin/recipe/ingredients/")
def admin_recipe_ingredients():
    recipe_id = request.args.get("recipe_id")
    ingredients_id = request.args.get("ing_id")
    ingredient = ""

    if ingredients_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "ingredients.id": ObjectId(ingredients_id)}},
            {
                "$project": {
                    "ingredients": {
                        "$filter": {
                            "input": "$ingredients",
                            "as": "ingredient",
                            "cond": {"$eq": ['$$ingredient.id', ObjectId(ingredients_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        ingredient = recipe[0]["ingredients"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/admin/ingredients.html", recipe=recipe, ingredient=ingredient)


# admin - add or update ingredients
@app.route("/admin/recipe/ingredients/", methods=['POST'])
def admin_recipe_ingredients_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        ingredient_id = request.form.get("ingredient_id")

        values = {
            "name": request.form.get("name"),
            "quantity": request.form.get("quantity"),
        }

        if ingredient_id:
            # update ingredient
            values["id"] = ObjectId(ingredient_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "ingredients.id": ObjectId(
                ingredient_id)}, {"$set": {"ingredients.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add ingredient
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"ingredients": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("admin_recipe_ingredients", recipe_id=recipe_id))


# admin - delete ingredients
@app.route("/admin/ingredient/delete/")
def admin_delete_ingredient():
    recipe_id = request.args.get("recipe_id")
    ingredient_id = request.args.get("ing_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"ingredients": {"id": ObjectId(ingredient_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("admin_recipe_ingredients", recipe_id=recipe_id))


# admin - directions
@app.route("/admin/recipe/directions/")
def admin_recipe_directions():
    recipe_id = request.args.get("recipe_id")
    direction_id = request.args.get("direction_id")
    direction = ""

    if direction_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "directions.id": ObjectId(direction_id)}},
            {
                "$project": {
                    "directions": {
                        "$filter": {
                            "input": "$directions",
                            "as": "direction",
                            "cond": {"$eq": ['$$direction.id', ObjectId(direction_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        direction = recipe[0]["directions"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/admin/directions.html", recipe=recipe, direction=direction)


# admin - add or update directions
@app.route("/admin/recipe/directions/", methods=['POST'])
def admin_recipe_directions_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        direction_id = request.form.get("direction_id")

        values = {
            "step": request.form.get("step"),
            "instruction": request.form.get("instruction"),
        }

        if direction_id:
            # update direction
            values["id"] = ObjectId(direction_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "directions.id": ObjectId(
                direction_id)}, {"$set": {"directions.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add direction
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"directions": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("admin_recipe_directions", recipe_id=recipe_id))


# admin - delete directions
@app.route("/admin/direction/delete/")
def admin_delete_directions():
    recipe_id = request.args.get("recipe_id")
    direction_id = request.args.get("direction_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"directions": {"id": ObjectId(direction_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("admin_recipe_directions", recipe_id=recipe_id))


# admin - nutritions
@app.route("/admin/recipe/nutritions/")
def admin_recipe_nutritions():
    recipe_id = request.args.get("recipe_id")
    nutrition_id = request.args.get("nutrition_id")
    nutrition = ""

    if nutrition_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "nutritional_information.id": ObjectId(nutrition_id)}},
            {
                "$project": {
                    "nutritional_information": {
                        "$filter": {
                            "input": "$nutritional_information",
                            "as": "nutritional_information",
                            "cond": {"$eq": ['$$nutritional_information.id', ObjectId(nutrition_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        nutrition = recipe[0]["nutritional_information"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/admin/nutritions.html", recipe=recipe, nutrition=nutrition)


# admin - add or update nutritions
@app.route("/admin/recipe/nutritions/", methods=['POST'])
def admin_recipe_nutritions_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        nutrition_id = request.form.get("nutrition_id")

        values = {
            "name": request.form.get("name"),
            "quantity": request.form.get("quantity"),
        }

        if nutrition_id:
            # update nutrition
            values["id"] = ObjectId(nutrition_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "nutritional_information.id": ObjectId(
                nutrition_id)}, {"$set": {"nutritional_information.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add nutrition
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"nutritional_information": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("admin_recipe_nutritions", recipe_id=recipe_id))


# admin - delete nutritions
@app.route("/admin/nutrition/delete/")
def admin_delete_nutrition():
    recipe_id = request.args.get("recipe_id")
    nutrition_id = request.args.get("nutrition_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"nutritional_information": {"id": ObjectId(nutrition_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("admin_recipe_nutritions", recipe_id=recipe_id))


# admin - approve user added recipe
@app.route("/admin/approve-recipe/<recipe_id>/")
def admin_approve_recipe(recipe_id):
    return_url = request.args.get("url")
    recipe = db.recipes.find_one({"_id": ObjectId(recipe_id)})
    if not recipe:
        return abort(404, "Recipe Not Found")

    result = db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                   "$set": {"status": RecipeStatus.Approved.value}})
    if result.modified_count > 0:
        flash("Approved Successfully", "success")
    else:
        flash("Error Approving Recipe", "danger")

    return redirect(return_url)


# admin - reject user added recipe
@app.route("/admin/reject-recipe/<recipe_id>/")
def admin_reject_recipe(recipe_id):
    return_url = request.args.get("url")
    recipe = db.recipes.find_one({"_id": ObjectId(recipe_id)})
    if not recipe:
        return abort(404, "Recipe Not Found")

    result = db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                   "$set": {"status": RecipeStatus.Rejected.value}})
    if result.modified_count > 0:
        flash("Rejected Successfully", "success")
    else:
        flash("Error Approving Recipe", "danger")

    return redirect(return_url)


# admin view user added recipes
@app.route("/admin/view-user-recipes/")
def admin_view_user_recipes():
    user_id = request.args.get("user_id")
    admin_id = session["user"]["_id"]["$oid"]
    filter = ""
    if (not user_id):
        filter = {"inserted_by": {"$ne": ObjectId(
            admin_id)}, "status": RecipeStatus.Approved.value}
    else:
        filter = {"inserted_by": ObjectId(
            user_id), "status": RecipeStatus.Approved.value}

    # approved recipes uploaded by user
    recipes = db.recipes.aggregate([
        {"$match": filter},
        {
            "$lookup": {
                "from": db.users.name,
                "localField": "inserted_by",
                "foreignField": "_id",
                "as": "user"
            }
        }
    ])
    return render_template("/admin/user-recipes.html", recipes=recipes)


# admin view rejected recipes
@app.route("/admin/view-rejected-recipes/")
def admin_view_rejected_recipes():
    admin_id = session["user"]["_id"]["$oid"]

    # approved recipes uploaded by user
    recipes = db.recipes.aggregate([
        {"$match": {"inserted_by": {"$ne": ObjectId(
            admin_id)}, "status": RecipeStatus.Rejected.value}},
        {
            "$lookup": {
                "from": db.users.name,
                "localField": "inserted_by",
                "foreignField": "_id",
                "as": "user"
            }
        }
    ])
    return render_template("/admin/rejected-recipes.html", recipes=recipes)

# admin - delete recipe


@app.route("/admin/delete-recipe/<recipe_id>/")
def admin_delete_recipe(recipe_id):
    return_url = request.args.get("url")
    recipe = db.recipes.find_one({"_id": ObjectId(recipe_id)})
    if not recipe:
        return abort(404, "Recipe Not Found")

    img_file_name = recipe['img_file_name']
    result = db.recipes.delete_one({"_id": ObjectId(recipe_id)})

    if result.deleted_count > 0:
        os.remove(APP_ROOT+"/images/recipes/"+img_file_name)
        flash("Recipe Deleted Successfully", "success")
    else:
        flash("Error deleting recipe", "success")

    return redirect(return_url)

# admin view registered users


@app.route("/admin/view-users/")
def admin_view_users():
    users = db.users.aggregate([
        {
            "$lookup": {
                "from": db.recipes.name,
                "localField": "_id",
                "foreignField": "inserted_by",
                "pipeline": [{
                    "$match": {"status": RecipeStatus.Approved.value}
                }],
                "as": "recipes"
            }
        },
        {
            "$project": {
                "full_name": "$full_name",
                "email": "$email",
                "contact_no": "$contact_no",
                "recipe_count": {"$size": "$recipes"}
            }
        }

    ])
    users = list(users)
    return render_template("/admin/users.html", users=users)


@app.route("/admin/delete-user/<user_id>/")
def admin_delete_user(user_id):
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return abort(404, "User Not Found")

    db.recipes.delete_many({"inserted_by": ObjectId(user['_id'])})
    db.users.delete_one({"_id": ObjectId(user['_id'])})
    flash("user deleted successfully", "success")

    return redirect(url_for("admin_view_users"))

# -------------------------------------------------------------------------------------------------------

# user routes


@app.route("/")
@app.route("/home/")
def index():
    categories = db.categories.find({})
    recent_recipes = db.recipes.find(
        {"status": RecipeStatus.Approved.value}).sort('_id', -1).limit(3)
    return render_template("index.html", categories=categories, recent_recipes=recent_recipes)


@app.route("/registration/", methods=['GET', 'POST'])
def user_registration():
    if request.method == "POST":
        values = {
            "full_name": request.form.get("full_name"),
            "email": request.form.get("email"),
            "contact_no": request.form.get("contact_no"),
            "password": request.form.get("password"),
            "is_active": True
        }
        result = db.users.insert_one(values)
        user = db.users.find_one({"_id": ObjectId(result.inserted_id)})
        if result.inserted_id:
            start_session(user)
            session["is_user"] = True

            flash("Registered successfully", "success")
            return redirect(url_for("index"))

    return render_template("/registration.html")

# user - login


@app.route("/login/", methods=["GET", "POST"])
def user_login():
    error_msg = ""
    if request.method == "POST":
        values = {
            "email": request.form.get("email"),
            "password": request.form.get("password")
        }
        user = db.users.find_one(values)
        if user:
            start_session(user)
            session["is_user"] = True

            return redirect(url_for("index"))
        else:
            error_msg = "Invalid Login Credentials"

    return render_template("/login.html", error_msg=error_msg)


# user - change password
@app.route("/change-password/", methods=['GET', 'POST'])
def user_change_password():
    user_id = session["user"]['_id']['$oid']
    if request.method == "POST":
        values = {
            "password": request.form.get("password"),
        }
        db.users.update_one({"_id": ObjectId(user_id)}, {"$set": values})
        flash("Password Updated successfully", "success")
        return redirect(url_for("user_change_password"))

    return render_template("/change-password.html")

# user - profile


@app.route("/profile/", methods=['GET', 'POST'])
def user_profile():
    user_id = session["user"]['_id']['$oid']
    if request.method == "POST":
        values = {
            "full_name": request.form.get("full_name"),
            "contact_no": request.form.get("contact_no"),
        }
        result = db.users.update_one(
            {"_id": ObjectId(user_id)}, {"$set": values})
        user = db.users.find_one({"_id": ObjectId(user_id)})
        start_session(user)
        flash("Profile Updated successfully", "success")
        return redirect(url_for("user_profile"))

    user = db.users.find_one({"_id": ObjectId(user_id)})
    return render_template("/profile.html", user=user)

# user recipes


@app.route("/my-recipes/")
@login_required
@user_only
def user_recipes():
    user_id = session['user']['_id']['$oid']
    recipes = db.recipes.aggregate([
        {"$match": {"inserted_by": ObjectId(user_id), "is_active": True}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }
        },
        {
            "$lookup": {
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "as": "sub_category"
            }
        }
    ])
    recipes = list(recipes)
    list.reverse(recipes)
    return render_template("/my-recipes.html", recipes=recipes, RecipeStatus=RecipeStatus)


@app.route("/add-recipe/", methods=['GET', 'POST'])
@login_required
@user_only
def user_add_recipe():
    user_id = session['user']['_id']['$oid']

    if request.method == "POST":
        image = request.files.get('recipe_image')
        values = {
            "category_id": ObjectId(request.form.get("category_id")),
            "sub_category_id": ObjectId(request.form.get("sub_category_id")),
            "recipe_title": request.form.get("recipe_title"),
            "servings": request.form.get("servings"),
            "cook_time": request.form.get("cook_time"),
            "description": request.form.get("description"),
            "ingredients": [],
            "directions": [],
            "nutritional_information": [],
            "img_file_name": image.filename,
            "inserted_by": ObjectId(user_id),
            "is_active": True,
            "status": RecipeStatus.Pending.value
        }
        result = db.recipes.insert_one(values)
        image.save(APP_ROOT+"/images/recipes/"+image.filename)
        flash("Recipe Added Successfully", "success")
        return redirect(url_for("user_recipe_ingredients", recipe_id=result.inserted_id))

    recipe = ""
    categories = db.categories.find({"is_active": True})
    sub_categories = db.sub_categories.find({"is_active": True})

    return render_template("/recipe-save.html", recipe=recipe, categories=categories, sub_categories=sub_categories)

# user - recipe - edit
@app.route("/edit-recipe/<recipe_id>/",  methods=['GET', 'POST'])
def user_edit_recipe(recipe_id):

    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        image = request.files.get('recipe_image')
        image_filename = request.form.get('img_file_name')

        if image.filename != "":
            image_filename = image.filename

        values = {
            "category_id": ObjectId(request.form.get("category_id")),
            "sub_category_id": ObjectId(request.form.get("sub_category_id")),
            "recipe_title": request.form.get("recipe_title"),
            "servings": request.form.get("servings"),
            "cook_time": request.form.get("cook_time"),
            "description": request.form.get("description"),
            "img_file_name": image_filename
        }

        db.recipes.update_one({"_id": ObjectId(recipe_id)}, {"$set": values})
        # Save recipe image if uploaded
        if image.filename != "":
            image.save(APP_ROOT+"/images/recipes/"+image.filename)

        flash("Recipe Updated Successfully", "success")
        return redirect(url_for("user_recipes"))

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    sub_categories = db.sub_categories.find({"is_active": True})
    categories = db.categories.find({"is_active": True})
    return render_template("/admin/recipe-save.html", recipe=recipe, categories=categories, sub_categories=sub_categories)


# user - ingredients
@app.route("/ingredients/")
def user_recipe_ingredients():
    recipe_id = request.args.get("recipe_id")
    ingredients_id = request.args.get("ing_id")
    ingredient = ""

    if ingredients_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "ingredients.id": ObjectId(ingredients_id)}},
            {
                "$project": {
                    "ingredients": {
                        "$filter": {
                            "input": "$ingredients",
                            "as": "ingredient",
                            "cond": {"$eq": ['$$ingredient.id', ObjectId(ingredients_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        ingredient = recipe[0]["ingredients"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/ingredients.html", recipe=recipe, ingredient=ingredient)


# user - add or update ingredients
@app.route("/ingredients/", methods=['POST'])
def user_recipe_ingredients_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        ingredient_id = request.form.get("ingredient_id")

        values = {
            "name": request.form.get("name"),
            "quantity": request.form.get("quantity"),
        }

        if ingredient_id:
            # update ingredient
            values["id"] = ObjectId(ingredient_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "ingredients.id": ObjectId(
                ingredient_id)}, {"$set": {"ingredients.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add ingredient
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"ingredients": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("user_recipe_ingredients", recipe_id=recipe_id))


# user - delete ingredients
@app.route("/ingredient/delete/")
def user_delete_ingredient():
    recipe_id = request.args.get("recipe_id")
    ingredient_id = request.args.get("ing_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"ingredients": {"id": ObjectId(ingredient_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("user_recipe_ingredients", recipe_id=recipe_id))


# user - directions
@app.route("/directions/")
def user_recipe_directions():
    recipe_id = request.args.get("recipe_id")
    direction_id = request.args.get("direction_id")
    direction = ""

    if direction_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "directions.id": ObjectId(direction_id)}},
            {
                "$project": {
                    "directions": {
                        "$filter": {
                            "input": "$directions",
                            "as": "direction",
                            "cond": {"$eq": ['$$direction.id', ObjectId(direction_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        direction = recipe[0]["directions"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/directions.html", recipe=recipe, direction=direction)


# user - add or update directions
@app.route("/directions/", methods=['POST'])
def user_recipe_directions_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        direction_id = request.form.get("direction_id")

        values = {
            "step": request.form.get("step"),
            "instruction": request.form.get("instruction"),
        }

        if direction_id:
            # update direction
            values["id"] = ObjectId(direction_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "directions.id": ObjectId(
                direction_id)}, {"$set": {"directions.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add direction
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"directions": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("user_recipe_directions", recipe_id=recipe_id))


# user - delete directions
@app.route("/direction/delete/")
def user_delete_directions():
    recipe_id = request.args.get("recipe_id")
    direction_id = request.args.get("direction_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"directions": {"id": ObjectId(direction_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("user_recipe_directions", recipe_id=recipe_id))


# user - nutritions
@app.route("/nutritions/")
def user_recipe_nutritions():
    recipe_id = request.args.get("recipe_id")
    nutrition_id = request.args.get("nutrition_id")
    nutrition = ""

    if nutrition_id:
        # edit
        recipe = db.recipes.aggregate([
            {"$match": {"_id": ObjectId(
                recipe_id), "nutritional_information.id": ObjectId(nutrition_id)}},
            {
                "$project": {
                    "nutritional_information": {
                        "$filter": {
                            "input": "$nutritional_information",
                            "as": "nutritional_information",
                            "cond": {"$eq": ['$$nutritional_information.id', ObjectId(nutrition_id)]}
                        }
                    }
                }
            }
        ])
        recipe = list(recipe)
        nutrition = recipe[0]["nutritional_information"][0]

    recipe = db.recipes.find_one(
        {"_id": ObjectId(recipe_id), "is_active": True})
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/nutritions.html", recipe=recipe, nutrition=nutrition)


# user - add or update nutritions
@app.route("/nutritions/", methods=['POST'])
def user_recipe_nutritions_post():
    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        recipe = db.recipes.find_one(
            {"_id": ObjectId(recipe_id), "is_active": True})

        nutrition_id = request.form.get("nutrition_id")

        values = {
            "name": request.form.get("name"),
            "quantity": request.form.get("quantity"),
        }

        if nutrition_id:
            # update nutrition
            values["id"] = ObjectId(nutrition_id)
            db.recipes.update_one({"_id": ObjectId(recipe['_id']), "nutritional_information.id": ObjectId(
                nutrition_id)}, {"$set": {"nutritional_information.$": values}})
            flash("Updated Successfully", "success")
        else:
            # add nutrition
            values["id"] = ObjectId()
            db.recipes.update_one({"_id": ObjectId(recipe['_id'])}, {
                                  "$push": {"nutritional_information": values}})
            flash("Added Successfully", "success")

        return redirect(url_for("user_recipe_nutritions", recipe_id=recipe_id))


# user - delete nutritions
@app.route("/nutrition/delete/")
def user_delete_nutrition():
    recipe_id = request.args.get("recipe_id")
    nutrition_id = request.args.get("nutrition_id")

    db.recipes.update_one({"_id": ObjectId(recipe_id)}, {
                          "$pull": {"nutritional_information": {"id": ObjectId(nutrition_id)}}})
    flash("Deleted Successfully", "success")
    return redirect(url_for("user_recipe_nutritions", recipe_id=recipe_id))


# user - view recipe details
@app.route("/view-recipe/<recipe_id>/")
@login_required
@user_only
def user_view_recipe(recipe_id):
    recipe = db.recipes.aggregate([
        {"$match": {"_id": ObjectId(recipe_id), "is_active": True}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "as": "category"
            }
        },
        {
            "$lookup": {
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "as": "sub_category"
            }
        }
    ])
    recipe = list(recipe)
    if not recipe:
        return abort(404, "Recipe Not Found")

    return render_template("/recipe-view.html", recipe=recipe[0])


# user - delete recipe
@app.route("/delete-recipe/<recipe_id>/")
def user_delete_recipe(recipe_id):
    recipe = db.recipes.find_one({"_id": ObjectId(recipe_id)})

    if not recipe:
        return abort(404, "Recipe Not Found")

    img_file_name = recipe['img_file_name']
    result = db.recipes.delete_one({"_id": ObjectId(recipe_id)})
    if result.deleted_count > 0:
        os.remove(APP_ROOT+"/images/recipes/"+img_file_name)
        flash("Recipe Deleted Successfully", "success")
    else:
        flash("Error deleting recipe", "success")
    return redirect(url_for("user_recipes"))


# user - view recipes by sub category
@app.route("/<category_name>/")
def view_sub_category_recipes_by_category_id(category_name):
    category_id = request.args.get("id")
    sub_cat_recipes = db.sub_categories.aggregate([
        {"$match": {"category_id": ObjectId(category_id)}},
        {
            "$lookup": {
                "from": db.recipes.name,
                "localField": "_id",
                "foreignField": "sub_category_id",
                "pipeline": [{
                    "$match": {"status": RecipeStatus.Approved.value}
                }],
                "as": "recipes"
            }
        }
    ])
    sub_cat_recipes = list(sub_cat_recipes)
    return render_template("sub-category-recipes.html", category_name=category_name, sub_cat_recipes=sub_cat_recipes)


# user - view recipe details
@app.route("/recipe-details/<recipe_id>/")
def view_recipe_details(recipe_id):
    recipe = db.recipes.aggregate([
        {"$match": {"_id": ObjectId(recipe_id)}},
        {
            "$lookup": {
                "from": db.categories.name,
                "localField": "category_id",
                "foreignField": "_id",
                "pipeline": [{
                    "$project": {"category_name": 1}
                }],
                "as": "category"
            }
        },
        {
            "$lookup": {
                "from": db.sub_categories.name,
                "localField": "sub_category_id",
                "foreignField": "_id",
                "pipeline": [{
                    "$project": {"sub_category_name": 1}
                }],
                "as": "sub_category"
            }
        }

    ])
    if not recipe:
        return abort(404, "Recipe Not Found")

    recipe = list(recipe)

    # get reviews for this recipe
    reviews = db.reviews.find({"recipe_id":ObjectId(recipe_id)}).sort("_id", -1)
    reviews = db.reviews.aggregate([
        {"$match":{"recipe_id":ObjectId(recipe_id)}},
        {
            "$lookup": {
                "from": db.review_comments.name,
                "localField": "_id",
                "foreignField": "review_id",
                "pipeline":[
                    {
                        "$lookup":{
                            "from":db.users.name,
                            "localField":"user_id",
                            "foreignField":"_id",
                            "as":"user"
                        }
                    },
                    {"$unwind":"$user"}
                ],
                "as": "comments"
            }
        }
    ])
    reviews = list(reviews)
    return render_template("/view-recipe-details.html", recipe=recipe[0], reviews=reviews)

# user add rating & review
@app.route("/add-review/", methods=['POST'])
def user_add_review():
    recipe_id = request.form.get("recipe_id")
    now = datetime.now()
    values = {
        "recipe_id":ObjectId(recipe_id),
        "rating":int(request.form.get("rating")),
        "review":request.form.get("review"),
        "posted_on":now
    }
    db.reviews.insert_one(values)
    flash("Ratings & Reviews added successfully", "success")
    return redirect(url_for("view_recipe_details", recipe_id=recipe_id))

# registered user add comments to review
@app.route("/add-review-comments/", methods=['POST'])
def user_add_review_comment():
    recipe_id = request.form.get("recipe_id")
    user_id = session["user"]["_id"]["$oid"]
    now = datetime.now()
    values = {
        "recipe_id":ObjectId(recipe_id),
        "user_id":ObjectId(user_id),
        "review_id":ObjectId(request.form.get("review_id")),
        "comment":request.form.get("comment"),
        "posted_on":now
    }
    db.review_comments.insert_one(values)
    flash("Comment added successfully", "success")
    return redirect(url_for("view_recipe_details", recipe_id=recipe_id))

@app.route("/search/")
def search():
    category_id = request.args.get('category')
    title = request.args.get('title')
    nutrition = request.args.get('nutrition')

    filter = {"status": RecipeStatus.Approved.value}

    if category_id:
        filter['category_id'] = ObjectId(category_id)

    if title:
        rgx_title = re.compile(".*" + title + ".*", re.IGNORECASE)
        filter['recipe_title'] = rgx_title

    if nutrition:
        rgx_nutrition = re.compile(".*" + nutrition + ".*", re.IGNORECASE)
        filter['nutritional_information.name'] = rgx_nutrition

    recipes = db.recipes.find(filter)

    categories = db.categories.find({})
    recipes=list(recipes)
    return render_template("/search.html", recipes=recipes, categories=categories, str=str)


@app.route("/logout/")
def logout():
    session.clear()
    return redirect(url_for("index"))

# get subcategories by category id


@app.route("/get-sub-categories")
def get_subcategories_by_category_id():
    category_id = request.args.get("category_id")
    sub_categories = db.sub_categories.find(
        {"category_id": ObjectId(category_id)})
    if sub_categories:
        return parse_json(sub_categories)
    else:
        return


# check user already registered using email address
@app.route("/is-user-email-exist")
def check_user_email_registerd():
    email = request.args.get("email")
    user = db.users.find_one({"email": email})
    if user:
        return jsonify(False)
    else:
        return jsonify(True)


if __name__ == '__main__':
    app.run(debug=True)
