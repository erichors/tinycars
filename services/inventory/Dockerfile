FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY Inventory.csproj .
RUN dotnet restore
COPY Program.cs .
RUN dotnet publish -c Release -o /out --no-restore

# Debian-based (glibc) runtime image: the OTel .NET auto-instrumentation default
# works without the linux-musl annotation needed for Alpine.
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /out .
EXPOSE 8083
ENTRYPOINT ["dotnet", "inventory.dll"]
