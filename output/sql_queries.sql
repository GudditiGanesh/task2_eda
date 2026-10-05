-- 01_kpis
SELECT COUNT(*) AS rows_, ROUND(SUM(total_sales),2) AS total_sales, ROUND(AVG(total_sales),2) AS avg_sales FROM sales;

-- 02_top_products
SELECT product, ROUND(SUM(total_sales),2) AS revenue, COUNT(*) AS orders FROM sales GROUP BY product ORDER BY revenue DESC LIMIT 10;

-- 03_monthly_sales
SELECT strftime('%Y-%m',order_date) AS month, ROUND(SUM(total_sales),2) AS revenue, COUNT(*) AS orders FROM sales GROUP BY month ORDER BY month;

-- 04_revenue_by_category
SELECT category, ROUND(SUM(total_sales),2) AS revenue, ROUND(AVG(total_sales),2) AS avg_sale FROM sales GROUP BY category ORDER BY revenue DESC;

-- 05_revenue_by_region
SELECT city, ROUND(SUM(total_sales),2) AS revenue, COUNT(*) AS orders FROM sales GROUP BY city ORDER BY revenue DESC;

-- 06_top_customers
SELECT customer_id, COUNT(*) AS orders, ROUND(SUM(total_sales),2) AS revenue FROM sales GROUP BY customer_id ORDER BY revenue DESC LIMIT 10;

-- 07_join_products_category
SELECT p.category, COUNT(DISTINCT p.product) AS products, ROUND(SUM(s.total_sales),2) AS revenue FROM sales s JOIN products p ON s.product = p.product GROUP BY p.category ORDER BY revenue DESC;

-- 08_join_customer_value
SELECT c.customer_id, c.first_order, COUNT(*) AS orders, ROUND(SUM(s.total_sales),2) AS lifetime_value FROM customers c JOIN sales s ON s.customer_id = c.customer_id GROUP BY c.customer_id ORDER BY lifetime_value DESC LIMIT 10;

