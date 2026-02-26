set default_storage_engine=InnoDB;

drop database if exists db_ninja_prd;
create database db_ninja_prd character set utf8mb4 collate utf8mb4_unicode_ci;  		-- 4byte UTF8 character set. 
																						-- Collation determines how strings are compared and sorted.
																						-- Unicode standard for sorting and comparisons here
																						-- ci for case insensitive
                                                                                        
use db_ninja_prd;

-- Table Definitions

create table enrollment_pin (
    pin_code varchar(50) primary key,
    is_active boolean not null default true,
    description varchar(255)
);

create table levels (
    level_id int primary key,
    level_name varchar(100) not null,
    unique_key_length int not null default 6, -- number of questions
    topic varchar(100) not null,
    is_available boolean not null default false -- controlled by admin page
);

create table users (
    user_id int primary key auto_increment,
    username varchar(50) unique not null,
    password_hash varchar(255) not null,
    registration_date timestamp default current_timestamp,
    current_level int default 1,
    highest_level int default 0,
    total_score int default 0,
    last_updated timestamp default current_timestamp,
    foreign key (current_level) references levels(level_id),
    foreign key (highest_level) references levels(level_id)
);

create table question (
    question_id int primary key auto_increment,
    level_id int not null,
    question_text text not null,
    option_a text not null, 
    option_b text not null, 
    option_c text not null, 
    option_d text not null,
    correct_option char(1) not null, -- 'a', 'b', 'c', 'd'
    foreign key (level_id) references levels(level_id)
);

create table user_session (
    session_id int primary key auto_increment,
    user_id int not null,
    level_id int not null,
    questions_data json not null, -- stores the randomized qs/options for integrity
    correct_key varchar(6), -- the unique combined answer string
    lives_remaining int default 3,
    session_score int not null default 0,
    is_active boolean default true,
    start_time timestamp default current_timestamp,
    foreign key (user_id) references users(user_id),
    foreign key (level_id) references levels(level_id)
);

-- Triggers
/*
-- automatically clear progress records if an admin resets a user to level 1
delimiter //

create trigger reset_progress_on_level_one_update
after update on users
for each row
begin
    -- only act if the level has been reduced to 1 from a higher level
    if new.current_level = 0 and old.current_level > 0 then
        -- delete all associated progress records
        delete from user_progress where user_id = new.user_id;
        
        -- also clear any active session data
        delete from user_session where user_id = new.user_id;
    end if;
end //

delimiter ;
*/
-- Stored Procedures

delimiter //

create procedure process_level_submission(
    in p_user_id int, 
    in p_level_id int, 
    in p_submitted_key varchar(100)
)
begin
    -- declare variables needed for checks/updates
    declare v_correct_key varchar(100);
    declare v_points_to_pass int;
    declare v_session_score int;
    declare v_current_lives int;
    
    -- start transaction
    start transaction;

    -- 1. retrieve data from usersession and lock the user row
    select final_submission_key, session_score into v_correct_key, v_session_score
    from user_session
    where user_id = p_user_id and level_id = p_level_id;

    select current_lives, total_score into v_current_lives, @v_total_score_old
    from users
    where user_id = p_user_id
    for update; -- prevents lost update problem (transaction ensures atomicity/isolation)
    

    -- 2. check if the submission is correct
    if v_correct_key is not null and p_submitted_key = v_correct_key then
        -- level passed!
        
        -- update userprogress (mark complete and record high score)
        insert into user_progress (user_id, level_id, high_score, is_completed)
        values (p_user_id, p_level_id, v_session_score, true)
        on duplicate key update 
            high_score = greatest(high_score, v_session_score), 
            is_completed = true;
            
        -- advance user to the next level, update score, and grant a life
        update users
        set 
            current_level = p_level_id + 1,
            total_score = total_score + v_session_score, -- total score is affected here!
            current_lives = current_lives + 1 -- grant a life for passing
        where user_id = p_user_id and current_level = p_level_id;
        
        -- log the attempt as successful
        insert into game_attempt (user_id, level_id, successful, lives_lost)
        values (p_user_id, p_level_id, true, 0);

        -- clean up the current session (key is no longer needed)
        delete from user_session where user_id = p_user_id;

        commit;
        select 'success' as status;

    else
        -- level failed! (incorrect answer)
        
        -- decrease user life (only if they have lives remaining)
        update user
        set current_lives = greatest(0, current_lives - 1)
        where user_id = p_user_id;
        
        -- log the attempt as failed, noting the life lost
        insert into game_attempt (user_id, level_id, successful, lives_lost)
        values (p_user_id, p_level_id, false, 1);

        -- clean up the session (user must restart the level with new key)
        delete from user_session where user_id = p_user_id;

        commit; -- commit the life deduction and session deletion
        select 'failure' as status;
    end if;

end //

delimiter ;

-- Insert Data

insert into enrollment_pin (pin_code, is_active, description)
values (754691, true, 'initial test enrollment key');

insert into levels (level_id, level_name, unique_key_length, topic, is_available)
values
(0, 'Newb', 0, 'Starting state', 1),
(1, 'White Belt', 6, 'DB Design', 0),
(2, 'Yellow Belt', 6, 'Querying', 0),
(3, 'Orange Belt', 6, 'Indexes', 0),
(4, 'Green Belt', 6, 'Transactions', 0),
(5, 'Blue Belt', 6, 'Isolation', 0),
(6, 'Purple Belt', 6, 'Locking', 0),
(7, 'Gold Belt', 6, 'Stored Procedures', 0),
(8, 'Brown Belt', 6, 'Replication', 0),
(9, 'Red Belt', 6, 'NoSQL', 0),
(10, 'Black Belt', 6, 'MongoDB aggregation', 0),
(11, 'Black Belt', 0, 'Game Completed', 1);

insert into question (level_id, question_text, option_a, option_b, option_c, option_d, correct_option) 
values 
(1, 'You store "DateOfBirth" and "CurrentAge" in the same table. Which Normal Form is primarily violated?', '1NF', '2NF', '3NF', 'BCNF', 'A'),
(1, 'A table has a Composite PK of (OrderID, ProductID). You add a column called "ProductDescription". What is the issue?', 'Transitive Dependency', 'Multi-valued Attribute', 'No Primary Key', 'Partial Functional Dependency', 'D'),
(1, 'To save space, you store multiple PhoneNumbers in a single comma-separated string column. What Rule of 1NF is broken?', 'Atomicity', 'No Primary Key', 'Unique column names', 'Transitive Dependency', 'A'),
(1, 'A table in 3NF is always also in:', '4NF', '1NF and 2NF', 'BCNF', '4NF and 5NF', 'B'),
(1, 'You have a ProjectTeam table which stores DeveloperID and ProjectName. The last developer on the "Mars Rover" project quits. When you delete their record, the "Mars Rover" project name and its metadata vanish from the system entirely. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Referential Leakage', 'A'),
(1, 'A single WarehouseStock table stores ProductID and CategorySafetyRules. You sell the very last "Chemical Solvent" in stock. When you delete that final inventory row, the database also wipes the safety protocols for the entire "Chemicals" category. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Cascade Fragmentation', 'A'),
(1, 'A Shipments table stores DriverName and TruckLicensePlate. A driver changes their name. You update 50 rows, but miss 5. Now the same truck appears to have two different drivers. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Multi-valued Dependency', 'C'),
(1, 'A Subscriptions table stores PlanName and MonthlyFee. The CEO raises the "Pro" price from €19 to €25. Your script has to update 10,000 rows but misses 50 due to a connection timeout. Now, some "Pro" users are billed €19 and others €25 for the same service. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Transactional Latency', 'C'),
(1, 'A Sales table stores BookTitle and AuthorBio. You stock a new Author, but you literally cannot add their name or Bio to the system until they sell their first book. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Null-Constraint Conflict', 'B'),
(1, 'A MovieLibrary table uses a composite PK of (Studio_ID, Movie_ID). You sign a deal with "A24 Studios" but because they haven't uploaded their first movie yet, you cannot even record the Studio's name or contact info in your system. This is an example of:', 'Deletion Anomaly', 'Insertion Anomaly', 'Update Anomaly', 'Schema Rigidity', 'B'),
(2, 'Level 2 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(2, 'Level 2 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(2, 'Level 2 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(2, 'Level 2 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(2, 'Level 2 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(2, 'Level 2 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(3, 'Level 3 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(3, 'Level 3 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(3, 'Level 3 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(3, 'Level 3 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(3, 'Level 3 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(3, 'Level 3 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(3, 'Level 3 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(4, 'Level 4 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(4, 'Level 4 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(4, 'Level 4 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(4, 'Level 4 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(4, 'Level 4 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(4, 'Level 4 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(4, 'Level 4 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(5, 'Level 5 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(5, 'Level 5 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(5, 'Level 5 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(5, 'Level 5 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(5, 'Level 5 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(5, 'Level 5 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(5, 'Level 5 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(6, 'Level 6 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(6, 'Level 6 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(6, 'Level 6 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(6, 'Level 6 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(6, 'Level 6 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(6, 'Level 6 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(6, 'Level 6 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(7, 'Level 7 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(7, 'Level 7 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(7, 'Level 7 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(7, 'Level 7 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(7, 'Level 7 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(7, 'Level 7 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(7, 'Level 7 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(8, 'Level 8 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(8, 'Level 8 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(8, 'Level 8 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(8, 'Level 8 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(8, 'Level 8 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(8, 'Level 8 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(8, 'Level 8 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(9, 'Level 9 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(9, 'Level 9 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(9, 'Level 9 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(9, 'Level 9 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(9, 'Level 9 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(9, 'Level 9 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(9, 'Level 9 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C'),
(10, 'Level 10 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(10, 'Level 10 Test 1', 'GET', 'EXTRACT', 'SELECT', 'OPEN', 'C'),
(10, 'Level 10 Test 2', 'All columns', 'All rows', 'Delete all', 'Filter data', 'A'),
(10, 'Level 10 Test 3', 'ORDER BY', 'WHERE', 'GROUP BY', 'LIMIT', 'B'),
(10, 'Level 10 Test 4', 'REMOVE', 'DELETE', 'DROP', 'TRUNCATE', 'D'),
(10, 'Level 10 Test 5', 'SELECT Students', 'SELECT * FROM Students', 'EXTRACT Students', 'SHOW Students', 'B'),
(10, 'Level 10 Test 6', 'MODIFY', 'SAVE', 'UPDATE', 'CHANGE', 'C');
