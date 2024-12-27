import urllib.parse
from flask import Flask, render_template, request
import mysql.connector
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Sruthi@12345",
    database="mydb",
    port="3306"
)

# Retrieve data from mobiles_search_history table


def truncate_title(title, length=50):
    return title[:length] + '...' if len(title) > length else title


def get_search_history():
    cursor = conn.cursor(dictionary=True)
    # Query to get the latest entry for each unique brand
    cursor.execute("""
    WITH RankedHistory AS (
    SELECT 
        LOWER(TRIM(LEFT(
            CASE 
                WHEN title LIKE '(Refurbished)%' THEN 
                    TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) -- Skip "(Refurbished)"
                ELSE 
                    title -- Original title
            END,
            CASE 
                WHEN LOCATE(' ', 
                    CASE 
                        WHEN title LIKE '(Refurbished)%' THEN 
                            TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                        ELSE 
                            title 
                    END) > 0 
                THEN 
                    LOCATE(' ', 
                        CASE 
                            WHEN title LIKE '(Refurbished)%' THEN 
                                TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                            ELSE 
                                title 
                        END) - 1 
                ELSE 
                    CHAR_LENGTH(
                        CASE 
                            WHEN title LIKE '(Refurbished)%' THEN 
                                TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                            ELSE 
                                title 
                        END) 
            END
        ))) AS brand_name, 
        title, 
        search_date_time,
        ROW_NUMBER() OVER (
            PARTITION BY LOWER(TRIM(LEFT(
                CASE 
                    WHEN title LIKE '(Refurbished)%' THEN 
                        TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                    ELSE 
                        title 
                END,
                CASE 
                    WHEN LOCATE(' ', 
                        CASE 
                            WHEN title LIKE '(Refurbished)%' THEN 
                                TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                            ELSE 
                                title 
                        END) > 0 
                    THEN 
                        LOCATE(' ', 
                            CASE 
                                WHEN title LIKE '(Refurbished)%' THEN 
                                    TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                                ELSE 
                                    title 
                            END) - 1 
                    ELSE 
                        CHAR_LENGTH(
                            CASE 
                                WHEN title LIKE '(Refurbished)%' THEN 
                                    TRIM(SUBSTRING(title, LOCATE(')', title) + 2)) 
                                ELSE 
                                    title 
                            END) 
                END
            ))) 
            ORDER BY search_date_time DESC
        ) AS `rank`
    FROM mobiles_search_history
)
SELECT *
FROM RankedHistory
WHERE `rank` = 1
ORDER BY search_date_time DESC
LIMIT 4;



    """)
    search_history = cursor.fetchall()
    cursor.close()

    for entry in search_history:
        entry['title'] = extract_mobile_name(entry['title'])

    return search_history


def extract_mobile_name(title):
    """
    Extracts the main mobile name from the title.
    Assumes the mobile name ends before the first '|' or '('.
    """
    if '|' in title:
        return title.split('|')[0].strip()
    if '(' in title:
        return title.split('(')[0].strip()
    return title.strip()

# Function to get ML-based recommendations based on search history


def get_ml_recommendations(search_history):
    cursor = conn.cursor(dictionary=True)

    # Fetch all mobile data to create the recommendation model
    cursor.execute("SELECT * FROM Mobiles")
    mobiles_data = cursor.fetchall()

    # Extract the mobile titles to use for recommendation
    titles = [extract_mobile_name(mobile['title']) for mobile in mobiles_data]

    # Initialize the TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(titles)

    # Generate recommendations based on cosine similarity
    recommendations = []
    seen_ids = set()  # Keep track of already recommended mobile IDs
    if search_history:
        # Extract the last search title
        last_search_title = extract_mobile_name(search_history[0]['title'])

        # Create the TF-IDF vector for the last search item
        last_search_tfidf = vectorizer.transform([last_search_title])

        # Calculate cosine similarities between the last search and all mobiles
        similarity_scores = cosine_similarity(last_search_tfidf, tfidf_matrix)

        # Get the top 4 similar items
        similar_indices = similarity_scores.argsort()[0][-5:][::-1]

        for index in similar_indices:
            mobile = mobiles_data[index]
            mobile['title'] = extract_mobile_name(mobile['title'])
            if mobile['title'] not in seen_ids:
                recommendations.append(mobile)
                # Mark this mobile as already recommended
                seen_ids.add(mobile['title'])

    cursor.close()
    return recommendations


@app.route('/', methods=['GET', 'POST'])
def index():
    selected_colours = []
    selected_conditions = []
    selected_memory = []
    selected_ram = []
    selected_ratings = []
    search_query = ''
    selected_sortby = ''
    selected_prices = []
    selected_delivery_times = []

    if request.method == 'POST':
        selected_colours = request.form.getlist('colour')
        selected_conditions = request.form.getlist('condition')
        selected_memory = request.form.getlist('memory')
        selected_ram = request.form.getlist('ram')
        selected_ratings = request.form.getlist('rating')
        search_query = request.form.get('search_query')
        selected_sortby = request.form.get('sortBy')
        selected_prices = request.form.getlist('price')
        selected_delivery_times = request.form.getlist('delivery')

        cursor = conn.cursor()

        # Start with a base query
        sql_query = "SELECT * FROM Mobiles WHERE 1"
        conditions = []
        params = []

        # Add conditions dynamically based on the filters provided
        if search_query:
            conditions.append("title LIKE %s")
            params.append('%' + search_query + '%')

        if selected_colours:
            conditions.append("colour IN (%s)" %
                              ', '.join(['%s'] * len(selected_colours)))
            params.extend(selected_colours)

        if selected_conditions:
            conditions.append("condition IN (%s)" %
                              ', '.join(['%s'] * len(selected_conditions)))
            params.extend(selected_conditions)

        if selected_memory:
            conditions.append("memory IN (%s)" %
                              ', '.join(['%s'] * len(selected_memory)))
            params.extend(selected_memory)

        if selected_ram:
            conditions.append("ram IN (%s)" %
                              ', '.join(['%s'] * len(selected_ram)))
            params.extend(selected_ram)

        if selected_ratings:
            conditions.append("rating IN (%s)" %
                              ', '.join(['%s'] * len(selected_ratings)))
            params.extend(selected_ratings)

        if selected_prices:
            conditions.append("price IN (%s)" %
                              ', '.join(['%s'] * len(selected_prices)))
            params.extend(selected_prices)

        if selected_delivery_times:
            conditions.append("delivery_time IN (%s)" %
                              ', '.join(['%s'] * len(selected_delivery_times)))
            params.extend(selected_delivery_times)

        # Combine the conditions with AND
        if conditions:
            sql_query += " AND " + " AND ".join(conditions)

        # Optionally, add sorting if the user selected a sort option
        if selected_sortby:
            sql_query += f" ORDER BY {selected_sortby}"

        # Execute the query
        cursor.execute(sql_query, params)
        mobile_data = cursor.fetchall()

        # Insert search data into search history
        insert_query = """
            INSERT INTO mobiles_search_history (title, platform_id, platform_name, price, rating, delivery_time, image_url, new_refurbished, search_date_time, redirect_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for mobile in mobile_data:
            cursor.execute(insert_query, (
                mobile[0],  # Assuming this is the title
                mobile[2],  # platform_id
                mobile[3],  # platform_name
                mobile[4],  # price
                mobile[5],  # rating
                mobile[6],  # delivery_time
                mobile[7],  # image_url
                mobile[8],  # new_refurbished
                datetime.now(),  # search_date_time
                mobile[1]   # redirect_link
            ))
        conn.commit()
        cursor.close()

        # Get search history and ML recommendations
        search_history_data = get_search_history()
        ml_recommendations = get_ml_recommendations(search_history_data)

        return render_template('mobiles3.html', mobile_data=mobile_data,
                               search_query=search_query, selected_colours=selected_colours,
                               selected_conditions=selected_conditions, selected_memory=selected_memory,
                               selected_ram=selected_ram, selected_ratings=selected_ratings,
                               selected_sortby=selected_sortby, selected_delivery_times=selected_delivery_times,
                               selected_prices=selected_prices, search_history_data=search_history_data,
                               recommendations=ml_recommendations)
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Mobiles")
        mobile_data = cursor.fetchall()
        cursor.close()

        search_history_data = get_search_history()
        ml_recommendations = get_ml_recommendations(search_history_data)

        return render_template('mobiles3.html', mobile_data=mobile_data,
                               search_query=search_query, selected_colours=selected_colours,
                               selected_conditions=selected_conditions, selected_memory=selected_memory,
                               selected_ram=selected_ram, selected_ratings=selected_ratings,
                               selected_sortby=selected_sortby, selected_delivery_times=selected_delivery_times,
                               selected_prices=selected_prices, search_history_data=search_history_data,
                               recommendations=ml_recommendations)

# Route to view search history


@app.route('/search_history')
def search_history():
    search_history_data = get_search_history()
    ml_recommendations = get_ml_recommendations(search_history_data)

    return render_template('mobiles3.html', search_history_data=search_history_data, recommendations=ml_recommendations)


@app.route('/mobile/<string:title>')
def mobile_details(title):
    cursor = conn.cursor(dictionary=True)

    # Sanitize the title for URL safety
    encoded_title = urllib.parse.quote(title)

    # Query to get mobile details based on the title
    query = "SELECT * FROM Mobiles WHERE title = %s"
    cursor.execute(query, (title,))
    mobile_data = cursor.fetchone()

    # Query to get search history for the mobiles
    history_query = "SELECT * FROM Mobiles_Search_History"
    cursor.execute(history_query)
    search_history_data = cursor.fetchall()

    cursor.close()

    if not mobile_data:
        return "Mobile not found!", 404

    # Render the details page, passing both mobile data and search history data
    return render_template(
        'mobiles3.html',
        mobile_data=mobile_data,  # single mobile details
        search_history_data=search_history_data,  # list of searched mobile data
        encoded_title=encoded_title  # Pass encoded title to JS
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)
