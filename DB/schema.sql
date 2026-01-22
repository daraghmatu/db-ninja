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

create table users (
    user_id int primary key auto_increment,
    username varchar(50) unique not null,
    password_hash varchar(128) not null,
    current_level int not null default 1,
    current_lives int not null default 3,
    total_score int not null default 0,
    registration_date timestamp default current_timestamp
);

create table level (
    level_id int primary key,
    name varchar(100) not null,
    unique_key_length int not null default 6, -- number of mcqs
    topic varchar(100) not null,
    is_available boolean not null default false -- controlled by admin page
);

create table question (
    question_id int primary key auto_increment,
    level_id int not null,
    question_text text not null,
    correct_answer char(1) not null, -- 'a', 'b', 'c', 'd'
    points_value int not null,
    foreign key (level_id) references level(level_id)
);

-- long-term record of best performance on each level
create table user_progress (
    user_id int,
    level_id int,
    high_score int not null default 0,
    is_completed boolean not null default false,
    completion_date timestamp default current_timestamp on update current_timestamp,
    primary key (user_id, level_id),
    foreign key (user_id) references users(user_id),
    foreign key (level_id) references level(level_id)
);

-- temporary, for randomized answers
create table user_session (
    session_id int primary key auto_increment,
    user_id int unique not null, -- only one active session per user
    level_id int not null,
    final_submission_key varchar(100) not null, -- the unique combined answer string
    questions_data json not null, -- stores the randomized qs/options for integrity
    session_score int not null default 0,
    foreign key (user_id) references users(user_id),
    foreign key (level_id) references level(level_id)
);

-- for analytics and the 'total lives lost' metric
create table game_attempt (
    attempt_id int primary key auto_increment,
    user_id int not null,
    level_id int not null,
    attempt_time timestamp default current_timestamp,
    successful boolean not null,
    lives_lost int not null default 0, -- 1 if failed, 0 if successful
    foreign key (user_id) references users(user_id)
);

-- Triggers

-- automatically clear progress records if an admin resets a user to level 1
delimiter //

create trigger reset_progress_on_level_one_update
after update on users
for each row
begin
    -- only act if the level has been reduced to 1 from a higher level
    if new.current_level = 1 and old.current_level > 1 then
        -- delete all associated progress records
        delete from user_progress where user_id = new.user_id;
        
        -- also clear any active session data
        delete from user_session where user_id = new.user_id;
    end if;
end //

delimiter ;

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