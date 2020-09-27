from DbConnector import DbConnector
from tabulate import tabulate
import os
from dataset import dataset
import numpy as np
import datetime
import json
import _pickle as pickle


class GeolifeProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor
        self.user_ids = {}
        self.labeled_ids = []
        self.activity_data = {}
        self.labeled_data = {}
        self.transportation_modes = ['walk', 'taxi', 'car', 'airplane', 'bike', 'subway', 'bus', 'train', 'other']

    def create_table(self, table_name):
        query = """CREATE TABLE IF NOT EXISTS %s (
                   id VARCHAR AUTO_INCREMENT NOT NULL PRIMARY KEY
                """
        # This adds table_name to the %s variable and executes the query
        self.cursor.execute(query % table_name)
        self.db_connection.commit()

    def load_labeled_ids(self):
        f = open('./dataset/dataset/labeled_ids.txt', 'r')
        for labeled_id in f:
            self.labeled_ids.append(labeled_id.split('\n')[0])

    def generate_user_ids(self, source_folder):
        for root, dirs, files in os.walk(source_folder, topdown=True):
            # for name in files:
            #     print(os.path.join(root, name))
            ids = []
            for name in dirs:
                if name != "Trajectory" and name != "Data":
                    ids.append(name)
            ids.sort()
            for id in ids:
                has_label = False
                if id in self.labeled_ids:
                    has_label = True
                self.user_ids[id] = has_label

    def print_user_ids(self):
        for pair in self.user_ids.items():
            print(pair)

    def create_user_table(self):
        query = """CREATE TABLE IF NOT EXISTS User (
                   id VARCHAR(3) NOT NULL PRIMARY KEY, has_labels BOOLEAN NOT NULL)
                """
        # This adds table_name to the %s variable and executes the query
        self.cursor.execute(query)
        self.db_connection.commit()

    def insert_user_data(self):
        for pair in self.user_ids.items():
            query = "INSERT INTO User (id, has_labels) VALUES ('%s', %s)"
            self.cursor.execute(query % (pair[0], pair[1]))
            self.db_connection.commit()

    def create_activity_table(self):
        query = """CREATE TABLE IF NOT EXISTS Activity (
                    id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                    user_id VARCHAR(3),
                    transportation_mode VARCHAR(30),
                    start_date_time DATETIME,
                    end_date_time DATETIME,
                    foreign key (user_id) references User(id))
                """
        self.cursor.execute(query)
        self.db_connection.commit()

    def insert_activity_data(self):
        count = 0
        for (user_id, activity_list) in self.activity_data.items():
            print("Queries finished: " + str(count) + "/181")
            count += 1
            print("Length: ", len(activity_list))
            if (len(activity_list) > 0):
                for counter, activity in enumerate(activity_list):
                    query = "INSERT INTO Activity (user_id, transportation_mode, start_date_time, end_date_time) VALUES ('%s', '%s', '%s', '%s')"
                    self.cursor.execute(
                        query % (user_id, activity[0][2], activity[0][5] + " " + activity[0][6], activity[-1][5] + " " + activity[-1][6]))
        self.db_connection.commit()

    # def reformat_time(date, time):
    #     year = date[:4]
    #     month = date[4:6]
    #     day = date[6:8]
    #     hour = time[8:10]
    #     min = time[10:12]
    #     sec = time[12:14]
    #     formated_time = year + "-" + month + "-" + day + " " + hour + ":" + min + ":" + sec
    #     return formated_time

    def create_trackpoint_table(self):
        query = """CREATE TABLE IF NOT EXISTS TrackPoint (
                    id INT AUTO_INCREMENT NOT NULL PRIMARY KEY,
                    activity_id INT,
                    lat DOUBLE,
                    lon DOUBLE,
                    altitude INT,
                    date_days DOUBLE,
                    date_time DATETIME,
                    foreign key (activity_id) references Activity(id))
                """
        self.cursor.execute(query)
        self.db_connection.commit()


# activity_data = {
#   user_id: activity_list = [
#               [lat, lon, null, alt, number_of_days_fractional, date_as_string, time_as_string],
#               [lat, lon, null, alt, number_of_days_fractional, date_as_string, time_as_string],
#           ...,
#               [lat, lon, null, alt, number_of_days_fractional, date_as_string, time_as_string]
#            ]
# }


    def generate_activity_data(self):
        number_of_labels = 0
        for user in self.user_ids.keys():
            print(user)
            activity_list = []
            for root, dirs, files in os.walk('./dataset/dataset/Data/' + user):
                for name in files:
                    tm = False
                    if (name != '.DS_Store' and name != 'labels.txt'):
                        num_lines = sum(1 for _ in open(root + '/' + name))
                        if(not(num_lines > 2506)):  # first six rows are bullshit and limit is 2500 rows of trackpoint-data
                            if (self.labeled_data.get(user)):
                                act_data = self.labeled_data.get(user)
                                for line in act_data:
                                    if name.replace(".plt", "") == line[0]:
                                        number_of_labels += 1
                                        print("Found label, label count is now", number_of_labels)
                                        tm = line[2]

                            activity_list.append(np.genfromtxt(root + '/' + name,
                                                               skip_header=6,
                                                               delimiter=',',
                                                               usecols=(0, 1, 2, 3, 4, 5, 6),
                                                               converters={2: (lambda x: tm if tm else "NULL"),
                                                                           3: (lambda x: int(x) if isinstance(x, int) else float(x)),
                                                                           5: (lambda x: str(x.decode("utf-8"))),
                                                                           6: (lambda x: str(x.decode('utf-8')))},  # max_rows=2500 removed due to causing wrong calculations
                                                               ).tolist())  # tolist for å slippe å styre med npliste
            self.activity_data[user] = activity_list
        print("Finished collecting user data from file system ")

    def write_activity_data_to_json(self):
        with open('activity_data.json', 'w') as file:
            json.dump(self.activity_data, file, sort_keys=True)

    def load_activity_data_from_json(self):
        with open('activity_data.json') as json_file:
            print("Loading data...")
            self.activity_data = json.load(json_file)
            print("Finished loading data from JSON file")
            # print(self.activity_data.get('181')[0])

    def find_start_end_times(self, user_id, activity_number):
        # First trackpoint in activity

        start = self.activity_data.get(user_id)[activity_number][0][4] + ' ' + \
            self.activity_data.get(user_id)[activity_number][0][5]
        # Last trackpoint in activity
        end = self.activity_data.get(user_id)[activity_number][-1][4] + ' ' + \
            self.activity_data.get(user_id)[activity_number][-1][5]
        return (start, end)


# labeled_data = {
#   user_id : [
#       [start_time, end_time, transportation_mode]
# ]
# }


    def generate_labeled_data(self):
        for root, dirs, files in os.walk("./dataset/dataset/Data", topdown=True):
            for name in dirs:
                if (name in self.labeled_ids):
                    path = os.path.join(root, name, "labels.txt")
                    data = np.genfromtxt(path,
                                         skip_header=1,
                                         delimiter='\t',
                                         usecols=(0, 1, 2),
                                         converters={
                                             0: (lambda x: str(x.decode("utf-8").replace('/', '-'))),
                                             1: (lambda x: str(x.decode('utf-8').replace('/', '-'))),
                                             2: (lambda x: str(x.decode('utf-8')))}).tolist()
                    if (len(data) == 3 and data[2] in self.transportation_modes):
                        liste = [data]
                        for i in range(0, len(liste)):
                            liste[i] = (liste[i][0].replace("-", "").replace(" ",
                                                                             "").replace(":", ""), liste[i][1], liste[i][2])
                        self.labeled_data[name] = liste
                    else:
                        for i in range(0, len(data)):
                            data[i] = (data[i][0].replace("-", "").replace(" ",
                                                                           "").replace(":", ""), data[i][1], data[i][2])
                        self.labeled_data[name] = data


def main():
    program = None
    try:
        program = GeolifeProgram()  # Init program
        print("Loading labeled ids...")
        program.load_labeled_ids()  # Create list of labeled user ids
        # # Traverse directory and store all user ids in dict with true/false labeled_id
        print("Generating user_ids ids...")
        program.generate_user_ids("./dataset/dataset")
        # program.print_user_ids()  # Control method to check data is correct ex ('000', False)
        # program.create_user_table()  # Create User table with columns (id, has_labels)
        # program.insert_user_data()  # Insert id and has_labels
        print("Generating labeled data...")
        program.generate_labeled_data()
        # print("Generating activity data...")
        # program.generate_activity_data()

        program.load_activity_data_from_json()

        # print(program.activity_data.get("105"))
        # print("Writing data to JSON...")
        # program.write_activity_data_to_json()
        program.create_activity_table()
        program.create_trackpoint_table()
        program.insert_activity_data()
        # print(program.get_transportation_mode('059', 1))
        # print(program.get_transportation_mode('067', 1))
        # print(program.get_transportation_mode('106', 1))

    except Exception as e:
        print("Error", e)


if __name__ == '__main__':
    main()
