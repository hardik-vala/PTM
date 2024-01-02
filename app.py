import streamlit as st

def main():
  # Set up the title of the app
  st.title("Simple Streamlit App")

  # Input from the user
  user_input = st.text_input("Enter some text")

  # Display the input
  if user_input:
    st.write("You entered:", user_input)

if __name__ == "__main__":
  main()
