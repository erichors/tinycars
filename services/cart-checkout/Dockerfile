FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src ./src
RUN mvn -q -B package dependency:copy-dependencies -DoutputDirectory=target/lib -DincludeScope=runtime

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/app.jar app.jar
COPY --from=build /src/target/lib ./lib
EXPOSE 8082
ENTRYPOINT ["java", "-cp", "app.jar:lib/*", "tinycars.Main"]
