import datetime

# Given a date string (e.g. "20150608"), returns the year, month, and day-of-year (e.g. June 8 is day #159 of the year)
def parse_date_string(date_string):
    dt = datetime.strptime(date_string, '%Y%m%d')
    day_of_year = dt.timetuple().tm_yday
    month = dt.timetuple().tm_month
    year = dt.timetuple().tm_year
    return year, month, day_of_year