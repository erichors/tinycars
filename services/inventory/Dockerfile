# The published application is framework-dependent IL, so the SDK build stage
# can run on the builder's native architecture. This avoids slow QEMU restores
# when producing amd64 images from an arm64 development machine.
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:8.0 AS build
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
