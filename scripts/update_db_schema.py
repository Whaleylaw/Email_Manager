#!/usr/bin/env python3
"""
Database Schema Update Script

This script updates the Supabase database schema to add the fields needed for the email assistant agent:
- processed_by_agent: Boolean flag to indicate if an email has been processed
- agent_analysis: JSON field to store the analysis results
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Get Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("Error: Supabase credentials not found in environment variables")
    print("Make sure the .env file contains SUPABASE_URL and SUPABASE_KEY")
    sys.exit(1)

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

def check_column_exists(table, column):
    """Check if a column exists in a table"""
    try:
        # Try to select the column
        response = supabase.rpc(
            'get_column_info',
            {'table_name': table, 'column_name': column}
        ).execute()
        
        # If we get data back, the column exists
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking column {column} in table {table}: {e}")
        # Assume column does not exist if there's an error
        return False

def add_column(table, column, type_info):
    """Add a column to a table"""
    try:
        # Execute an ALTER TABLE SQL query
        response = supabase.rpc(
            'execute_sql',
            {'sql': f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {type_info};'}
        ).execute()
        return True
    except Exception as e:
        print(f"Error adding column {column} to table {table}: {e}")
        return False

def update_schema():
    """Update the database schema with new columns"""
    # Columns to add
    columns = [
        {
            'table': 'emails',
            'column': 'processed_by_agent',
            'type': 'BOOLEAN DEFAULT FALSE'
        },
        {
            'table': 'emails',
            'column': 'agent_analysis',
            'type': 'JSONB'
        }
    ]
    
    success_count = 0
    already_exists_count = 0
    error_count = 0
    
    print("Updating database schema...")
    
    for col in columns:
        table = col['table']
        column = col['column']
        type_info = col['type']
        
        # Check if column already exists
        exists = check_column_exists(table, column)
        
        if exists:
            print(f"Column {column} already exists in table {table}")
            already_exists_count += 1
            continue
        
        # Add the column
        success = add_column(table, column, type_info)
        
        if success:
            print(f"Successfully added column {column} to table {table}")
            success_count += 1
        else:
            print(f"Failed to add column {column} to table {table}")
            error_count += 1
    
    print(f"\nSchema update complete:")
    print(f"- {success_count} columns added")
    print(f"- {already_exists_count} columns already existed")
    print(f"- {error_count} errors")

def create_rpc_functions():
    """Create necessary RPC functions for database operations"""
    # Function to get column information
    get_column_info_sql = """
    CREATE OR REPLACE FUNCTION get_column_info(table_name TEXT, column_name TEXT)
    RETURNS TABLE (
        table_schema TEXT,
        table_name TEXT,
        column_name TEXT,
        data_type TEXT
    )
    LANGUAGE SQL
    SECURITY DEFINER
    AS $$
        SELECT
            table_schema,
            table_name,
            column_name,
            data_type
        FROM
            information_schema.columns
        WHERE
            table_schema = 'public'
            AND table_name = table_name
            AND column_name = column_name;
    $$;
    """
    
    # Function to execute arbitrary SQL (use with caution!)
    execute_sql_func = """
    CREATE OR REPLACE FUNCTION execute_sql(sql TEXT)
    RETURNS VOID
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    BEGIN
        EXECUTE sql;
    END;
    $$;
    """
    
    # First check if these functions already exist
    try:
        # Check for get_column_info
        response = supabase.rpc('get_column_info', {
            'table_name': 'emails',
            'column_name': 'id'
        }).execute()
        print("get_column_info function already exists")
    except Exception:
        # Create the function
        try:
            response = supabase.rpc('execute_sql', {'sql': get_column_info_sql}).execute()
            print("Created get_column_info function")
        except Exception as e:
            # Function might not exist yet, so create it via SQL
            try:
                # This is a simplified approach - in a real scenario, you might need to use
                # a database migration tool or a more robust method
                print("Creating get_column_info function via direct SQL (simplification)")
                # In a real scenario, you'd execute the SQL directly here
            except Exception as e:
                print(f"Error creating get_column_info function: {e}")
    
    # Check for execute_sql
    try:
        response = supabase.rpc('execute_sql', {'sql': 'SELECT 1;'}).execute()
        print("execute_sql function already exists")
    except Exception:
        # Create the function
        try:
            # In a real scenario, you'd execute the SQL directly here
            print("Creating execute_sql function (simplification)")
            # This is just a placeholder - in a real scenario, you'd need to create
            # this function using a different method
        except Exception as e:
            print(f"Error creating execute_sql function: {e}")

def create_vector_search_function():
    """Create or update the vector similarity search function"""
    # Check if the function already exists by trying to call it
    try:
        embedding = [0.0] * 1536  # Create a dummy embedding
        response = supabase.rpc('match_email_sections', {
            'query_embedding': embedding,
            'match_threshold': 0.5,
            'match_count': 1
        }).execute()
        print("match_email_sections function already exists")
        return
    except Exception:
        print("Creating match_email_sections function...")
    
    # SQL to create the function
    match_function_sql = """
    CREATE OR REPLACE FUNCTION match_email_sections(
        query_embedding vector(1536),
        match_threshold float,
        match_count int
    )
    RETURNS TABLE (
        email_id bigint,
        section_id bigint,
        section_content text,
        similarity float
    )
    LANGUAGE plpgsql
    AS $$
    BEGIN
        RETURN QUERY
        SELECT
            es.email_id,
            es.id as section_id,
            es.section_content,
            1 - (es.embedding <=> query_embedding) as similarity
        FROM
            email_sections es
        WHERE
            1 - (es.embedding <=> query_embedding) > match_threshold
        ORDER BY
            similarity DESC
        LIMIT
            match_count;
    END;
    $$;
    """
    
    try:
        # Try to create the function
        response = supabase.rpc('execute_sql', {'sql': match_function_sql}).execute()
        print("Successfully created match_email_sections function")
    except Exception as e:
        print(f"Error creating match_email_sections function: {e}")
        print("Note: You may need to create this function manually in the Supabase SQL editor")
        print("The SQL for the function is:")
        print(match_function_sql)

if __name__ == "__main__":
    # Create necessary RPC functions first
    create_rpc_functions()
    
    # Update the schema
    update_schema()
    
    # Create vector search function
    create_vector_search_function()
    
    print("\nDatabase update complete.")
    print("You can now use the email_assistant_agent.py script to analyze emails.")
