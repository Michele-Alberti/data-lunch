#!/bin/bash
 
 if [[ "$PANEL_ENV" == "production" ]]; then
    # Before starting set up the dynamic dns
    # First call
    mkdir -p ~/duckdns
    echo url=${DUCKDNS_URL} | curl -k -o ~/duckdns/duck.log -K -
    # Set the cronjob
    croncmd="echo url=\"${DUCKDNS_URL}\" | curl -k -o ~/duckdns/duck.log -K -"
    cronjob="*/5 * * * * $croncmd"
    ( crontab -l | grep -v -F "$croncmd" || : ; echo "$cronjob" ) | crontab -

    # Start nginx and certbot with simple configurations just to retrieve 
    # the SSL certificate
    docker compose -f ./docker/docker-compose-initiate.yaml --project-directory . up -d nginx
    docker compose -f ./docker/docker-compose-initiate.yaml --project-directory . up certbot
    docker compose -f ./docker/docker-compose-initiate.yaml --project-directory . down
 
    # Create cronjob for certbot and nginx
    # Renew certificates
    croncmd="cd /app && docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . up certbot"
    cronjob="0 3 * * * $croncmd"
    ( crontab -l | grep -v -F "$croncmd" || : ; echo "$cronjob" ) | crontab -
    # Update nginx
    croncmd="cd /app && docker compose -p ${PROJECTNAME} -f docker/docker-compose.yaml --project-directory . exec nginx nginx -s reload"
    cronjob="30 3 * * * $croncmd"
    ( crontab -l | grep -v -F "$croncmd" || : ; echo "$cronjob" ) | crontab -

    # Install Let's Encrypt best practice SSL potions
    curl https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > ./ssl/conf/options-ssl-nginx.conf

    # Delete dhparam if older than 30 days
    find ./ssl/conf/ -name "ssl-dhparams.pem" -type f -mtime +15 -delete 

    # Install dhparams (if missing)
	if [[ ! -f ./ssl/conf/ssl-dhparams.pem ]]; then
		echo "building dhparam"
		openssl dhparam -out ./ssl/conf/ssl-dhparams.pem 2048
	else
		echo "dhparam already exists"
	fi
else
    make ssl-gen-certificate
fi