FROM public.ecr.aws/nginx/nginx-unprivileged:1.29-alpine
USER 0
RUN apk upgrade --no-cache
USER 101
COPY html/ /usr/share/nginx/html/
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
ENV BAG_API_URL=http://bag-api:8000
EXPOSE 8080
