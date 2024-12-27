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

# Function to get search history from the database


def get_search_history():
    cursor = conn.cursor(dictionary=True)
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
    FROM cases_search_history
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
        entry['title'] = extract_case_name(entry['title'])

    return search_history


def extract_case_name(title):
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

    # Fetch all case data to create the recommendation model
    cursor.execute("SELECT * FROM Cases")
    case_data = cursor.fetchall()

    # Extract the mobile titles to use for recommendation
    titles = [extract_case_name(case['title']) for case in case_data]

    # Initialize the TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(titles)

    # Generate recommendations based on cosine similarity
    recommendations = []
    seen_ids = set()  # Keep track of already recommended mobile IDs
    if search_history:
        # Extract the last search title
        last_search_title = extract_case_name(search_history[0]['title'])

        # Create the TF-IDF vector for the last search item
        last_search_tfidf = vectorizer.transform([last_search_title])

        # Calculate cosine similarities between the last search and all cases
        similarity_scores = cosine_similarity(last_search_tfidf, tfidf_matrix)

        # Get the top 4 similar items
        similar_indices = similarity_scores.argsort()[0][-5:][::-1]

        for index in similar_indices:
            case = case_data[index]
            case['title'] = extract_case_name(case['title'])
            if case['title'] not in seen_ids:
                recommendations.append(case)
                # Mark this case as already recommended
                seen_ids.add(case['title'])

    cursor.close()
    return recommendations


@app.route('/', methods=['GET', 'POST'])
def index():
    selected_colours = []
    selected_conditions = []
    selected_materials = []
    selected_ratings = []
    search_query = ''
    selected_sortby = ''
    selected_prices = []
    selected_delivery_times = []

    if request.method == 'POST':
        selected_colours = request.form.getlist('colour')
        selected_conditions = request.form.getlist('condition')
        selected_materials = request.form.getlist('material')
        selected_ratings = request.form.getlist('rating')
        search_query = request.form.get('search_query')
        selected_sortby = request.form.get('sortBy')
        selected_prices = request.form.getlist('price')
        selected_delivery_times = request.form.getlist('delivery')

        cursor = conn.cursor()

        sql_query = "SELECT * FROM Cases WHERE 1"
        conditions = []
        params = []

        if search_query:
            conditions.append("title LIKE %s")
            params.append('%' + search_query + '%')

        # Add conditions for other filters like colour, material, etc.
        if selected_colours:
            colour_conditions = ["title LIKE %s" for _ in selected_colours]
            conditions.append("(" + " OR ".join(colour_conditions) + ")")
            params.extend(['%' + colour + '%' for colour in selected_colours])

        if selected_conditions:
            condition_conditions = [
                "new_refurbished = %s" for _ in selected_conditions]
            conditions.append("(" + " OR ".join(condition_conditions) + ")")
            params.extend(selected_conditions)

        if selected_materials:
            material_conditions = ["title LIKE %s" for _ in selected_materials]
            conditions.append("(" + " OR ".join(material_conditions) + ")")
            params.extend(
                ['%' + material + '%' for material in selected_materials])

        if selected_ratings:
            rating_conditions = []
            for rating_value in selected_ratings:
                if rating_value == '4':
                    rating_conditions.append(
                        "CAST(SUBSTRING_INDEX(rating, ' ', 1) AS DECIMAL(5,1)) >= 4.0")
                elif rating_value == '3':
                    rating_conditions.append(
                        "CAST(SUBSTRING_INDEX(rating, ' ', 1) AS DECIMAL(5,1)) >= 3.0")
                elif rating_value == '2':
                    rating_conditions.append(
                        "CAST(SUBSTRING_INDEX(rating, ' ', 1) AS DECIMAL(5,1)) >= 2.0")
                elif rating_value == '1':
                    rating_conditions.append(
                        "CAST(SUBSTRING_INDEX(rating, ' ', 1) AS DECIMAL(5,1)) >= 1.0")
            if rating_conditions:
                conditions.append("(" + " OR ".join(rating_conditions) + ")")

        if selected_prices:
            price_conditions = []
            for price_range in selected_prices:
                if price_range == 'below200':
                    price_conditions.append("price < 200")
                elif price_range == '200to500':
                    price_conditions.append("price BETWEEN 200 AND 500")
                elif price_range == 'above500':
                    price_conditions.append("price > 500")
            if price_conditions:
                conditions.append("(" + " OR ".join(price_conditions) + ")")

        if selected_delivery_times:
            delivery_conditions = []
            for delivery_time in selected_delivery_times:
                if delivery_time == 'within3days':
                    delivery_conditions.append("delivery_time <= 3")
                elif delivery_time == '3to7days':
                    delivery_conditions.append("delivery_time BETWEEN 3 AND 7")
                elif delivery_time == 'morethan7days':
                    delivery_conditions.append("delivery_time > 7")
            if delivery_conditions:
                conditions.append("(" + " OR ".join(delivery_conditions) + ")")

        if conditions:
            sql_query += " AND " + " AND ".join(conditions)

        cursor.execute(sql_query, params)
        case_data = cursor.fetchall()

        # Adding the searches into cases_search_history table
        insert_query = """
            INSERT INTO cases_search_history (title, platform_id, platform_name, price, rating, delivery_time, image_url, search_date_time, redirect_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        for case in case_data:
            cursor.execute(insert_query, (
                case[0],
                case[2],
                case[3],
                case[4],
                case[5],
                case[6],
                case[7],
                datetime.now(),
                case[1]
            ))
        conn.commit()
        cursor.close()

        # Get search history and recommendations
        search_history_data = get_search_history()
        recommendations = get_ml_recommendations(search_history_data)

        return render_template('case3.html', case_data=case_data,
                               search_query=search_query, selected_colours=selected_colours,
                               selected_conditions=selected_conditions, selected_materials=selected_materials,
                               selected_ratings=selected_ratings, selected_sortby=selected_sortby,
                               selected_prices=selected_prices, selected_delivery_times=selected_delivery_times,
                               search_history_data=search_history_data, recommendations=recommendations)
    else:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cases")
        case_data = cursor.fetchall()
        cursor.close()

        search_history_data = get_search_history()
        recommendations = get_ml_recommendations(search_history_data)

        return render_template('case3.html', case_data=case_data,
                               search_query=search_query, selected_colours=selected_colours,
                               selected_conditions=selected_conditions, selected_materials=selected_materials,
                               selected_ratings=selected_ratings, selected_sortby=selected_sortby,
                               selected_prices=selected_prices, selected_delivery_times=selected_delivery_times,
                               search_history_data=search_history_data, recommendations=recommendations)

# Route to view search history


@app.route('/search_history')
def search_history():
    search_history_data = get_search_history()
    recommendations = get_ml_recommendations(search_history_data)

    return render_template('cases.html', search_history_data=search_history_data, recommendations=recommendations)


if __name__ == '__main__':
    app.run(debug=True, port=5002)
