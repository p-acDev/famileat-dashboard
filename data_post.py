import pandas as pd
import pgeocode
nomi = pgeocode.Nominatim('fr')
import plotly.express as px
import streamlit as st
st.set_page_config(layout="wide")

# dict for corresp on statut and name in df column name
CORRESP_STATUT = {
    "Livré": "nbre_colis_livres",
    "Non Livré": "nbre_colis_non_livres",
    "Retard": "nbre_colis_livres_Retard",
    "Erreur colisage": "nbre_colis_livres_Erreur colisage"
}

def clean_data(df_raw):
    
    df = df_raw.copy()
    df = df.drop_duplicates()
    
    df["statut_livraison"] = df["Filtre ‡ appliquer"]
    # ensure 5 digit in code postale
    df["Code postal destinataire"] = df["Code postal destinataire"].astype('str').apply(lambda elem:elem.zfill(5))
    
    # low case for erreur colissage
    df["Erreur de colissage/Manque"] = df["Erreur de colissage/Manque"].apply(lambda elem:elem.lower())
    
    df.drop(columns=["Filtre ‡ appliquer", "No de ligne"], inplace=True)
    
    return df
    
def delivered_by_city(df, statut_livraison, livraison_condition=None):        
    # find the number of colis per city DELIVERED or UNDELIVERED
    
    if statut_livraison == "Livré":
        df_delivered = df[df["statut_livraison"] == "Livré"]
        if livraison_condition == "Retard":
            df_delivered = df_delivered[df_delivered["Retard"] == "oui"] # show only delay for delivered colis
        elif livraison_condition == "Erreur colisage":
            df_delivered = df_delivered[df_delivered["Erreur de colissage/Manque"] == "oui"]
    else:
        df_delivered = df[df["statut_livraison"] != "Livré"]
    
    series_delivered_count = df_delivered.groupby("Code postal destinataire")["statut_livraison"].count()
    df_delivered_count = nomi.query_postal_code(series_delivered_count.index.values)
    
    if livraison_condition:
        df_delivered_count[f"{CORRESP_STATUT[statut_livraison]}_{livraison_condition}"] = series_delivered_count.values
    else:    
        df_delivered_count[CORRESP_STATUT[statut_livraison]] = series_delivered_count.values
    
    # ensure that ville destinataire is used
    df_city_code = df[["Code postal destinataire", "Ville destinataire"]].drop_duplicates()
    df_city_code["postal_code"] = df_city_code["Code postal destinataire"]
    
    # delivered
    df_delivered_count = df_delivered_count.merge(df_city_code, how="left", on="postal_code")
    
    return df_delivered_count

def delivered_by_solution(df):
    
    delivered_by_solution = df.groupby("Solution")["Solution"].count()
    delivered_by_solution.columns = ["Nombre de livraison par solution"]
    
    return delivered_by_solution

def map_delivered_by_city(df, statut_livraison, livraison_condition=None):
    
    if livraison_condition:
        column_name = f"{CORRESP_STATUT[statut_livraison]}_{livraison_condition}"
    else:    
        column_name = CORRESP_STATUT[statut_livraison] 
    
    fig = px.scatter_mapbox(
    data_frame=df,
    lat=df['latitude'], lon=df['longitude'],
    mapbox_style = 'open-street-map',
    size=column_name,
    hover_name='Ville destinataire',
    zoom=4,
    color=column_name,
    color_continuous_scale=px.colors.sequential.Bluered,
    )
    
    
    return fig

if __name__ == "__main__":
    
    st.title("Dashboard")
    
    # extract the data from the excel file
    st.markdown("## Fichier d'entrée")
    with st.expander("Upload"):
        raw_data_file = st.file_uploader("Envoyer votre fichier")
    
    if raw_data_file is not None:
        st.markdown("## Statistiques générales")
        
        df_raw_data = pd.read_excel(raw_data_file)
        df = clean_data(df_raw_data)
        
        # first intro dashboard
        with st.container():
            n_comands = df.shape[0]
            n_delivered = df[df["statut_livraison"] == "Livré"].shape[0]
            n_undelivered = df[df["statut_livraison"] != "Livré"].shape[0]
            n_error_colissage = df[df["Erreur de colissage/Manque"] == "oui"].shape[0]
            n_delay = df[df["Retard"] == "oui"].shape[0]
            
            st.info(f'{n_comands} commandes au total', icon="ℹ️")
            
            col1, col2 = st.columns(2)

            with col1:
                st.success(f'{n_delivered} commandes livrées avec succés, soit {round(n_delivered/n_comands*100, 1)} %',
                           icon="✅")
            with col2:
                st.error(f'{n_undelivered} commandes non livrées, soit {round(n_undelivered/n_comands*100, 1)} %',
                         icon="🚨")
            
            col1, col2 = st.columns(2)
            with col1:
                st.warning(f'{n_delay} livraisons avec retard, soit {round(n_delay/n_delivered*100, 1)} %',
                           icon="⚠️")
            with col2:
                st.error(f'{n_error_colissage} livraisons avec erreur colissage, soit {round(n_error_colissage/n_delivered*100, 1)} %',
                         icon="🚨")
        
        # delivered by city container
        with st.container():
            st.markdown("## Statistiques par ville")
            
            df_delivered_by_city = delivered_by_city(df, "Livré")
            df_undelivered_by_city = delivered_by_city(df, "Non Livré") # undelivered will be everything expect "Livré"
            df_delay_by_city = delivered_by_city(df, "Livré", "Retard") 
            df_error_by_city = delivered_by_city(df, "Livré", "Erreur colisage")
            
            fig_delivered_by_city = map_delivered_by_city(df_delivered_by_city, "Livré")
            fig_undelivered_by_city = map_delivered_by_city(df_undelivered_by_city, "Non Livré")
            fig_delay_by_city = map_delivered_by_city(df_delay_by_city, "Livré", "Retard")
            fig_error_by_city = map_delivered_by_city(df_error_by_city, "Livré", "Erreur colisage")
             
                    
            if st.checkbox("Voir les données des colis livrés"):
                st.dataframe(df_delivered_by_city[["Ville destinataire", CORRESP_STATUT["Livré"], "place_name", "state_name", "county_name", "county_code"]])

            if st.checkbox("Voir les données des colis non livrés"):
                st.dataframe(df_undelivered_by_city[["Ville destinataire", CORRESP_STATUT["Non Livré"], "place_name", "state_name", "county_name", "county_code"]])

            if st.checkbox("Voir les données des livraison avec retard"):
                st.dataframe(df_delay_by_city[["Ville destinataire", CORRESP_STATUT["Retard"], "place_name", "state_name", "county_name", "county_code"]])

            if st.checkbox("Voir les données des livraisons avec erreur colisage"):
                st.dataframe(df_error_by_city[["Ville destinataire", CORRESP_STATUT["Erreur colisage"], "place_name", "state_name", "county_name", "county_code"]])

            #do the interactive plot of delivered colis
            hist = px.histogram(df.sort_values(by="Ville destinataire"), x="Ville destinataire", title="Distribution des commandes dans les Villes")
            st.plotly_chart(hist, use_container_width=True)
            
            plot_choice = st.radio(
                "Sélectionner ce que vous voulez voir apparaître sur la carte",
                ('Livré', 'Non livré', 'Retard', 'Erreur colisage'))
            if plot_choice == "Livré":
                st.plotly_chart(fig_delivered_by_city, use_container_width=True)
            elif plot_choice == "Non livré":
                st.plotly_chart(fig_undelivered_by_city, use_container_width=True)
            elif plot_choice == "Retard":
                st.plotly_chart(fig_delay_by_city, use_container_width=True)
            elif plot_choice == "Erreur colisage":
                st.plotly_chart(fig_error_by_city, use_container_width=True)
        
        # stats by solution
        with st.container():
            st.markdown("## Statistiques par livreur")
            df_by_solution = delivered_by_solution(df)
            df_by_solution_delivered = delivered_by_solution(df[df["statut_livraison"] == "Livré"])
            df_by_solution_delivered_taux = df_by_solution_delivered/df_by_solution * 100
            
            df_by_solution_delivered_delay = delivered_by_solution(df[(df["statut_livraison"] == "Livré") & (df["Retard"] == "oui")])
            df_by_solution_delivered_delay_taux = df_by_solution_delivered_delay/df_by_solution_delivered * 100
            
            if st.checkbox("Voir le nombre de livraison prises en charges par livreur"):
                st.dataframe(df_by_solution)
            
            hist_by_solution = px.histogram(df, x="Solution", title="Nombre de livraisons prises en charges par livreur")
            st.plotly_chart(hist_by_solution, use_container_width=True)
            
            if st.checkbox("Voir le nombre de livraisons avec succés par livreur"):
                st.dataframe(df_by_solution_delivered)
                
            if st.checkbox("Voir le taux de livraison par livreur"):
                st.dataframe(df_by_solution_delivered_taux.apply(lambda elem: f"{round(elem, 1)} %"))
        
            bar_taux_delivered = px.bar(df_by_solution_delivered_taux, title="Taux de livraison par livreur")
            st.plotly_chart(bar_taux_delivered, use_container_width=True)
            
            if st.checkbox("Voir le nombre de livraisons en retard par livreur"):
                st.dataframe(df_by_solution_delivered_delay)
            
            hist_by_solution_delay = px.histogram(df[(df["statut_livraison"] == "Livré") & (df["Retard"] == "oui")], x="Solution",
                                                  title="Nombre de livraisons en retard par livreur")
            st.plotly_chart(hist_by_solution_delay, use_container_width=True)
              