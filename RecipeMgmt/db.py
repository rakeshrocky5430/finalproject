from bson import ObjectId
import pymongo

dbClient = pymongo.MongoClient('mongodb://localhost:27017/')
db = dbClient["recipe"]

admin = db['admin']
users = db['users']
categories = db['categories']
sub_categories = db['sub_categories']
recipes = db['recipes']
reviews = db['reviews']
review_comments = db['review_comments']