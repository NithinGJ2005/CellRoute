-- PostGIS Schema Setup
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE towers (
    id SERIAL PRIMARY KEY,
    radio VARCHAR(10),
    mcc INT,
    net INT,
    area INT,
    cell BIGINT,
    unit INT,
    lon FLOAT,
    lat FLOAT,
    range INT,
    samples INT,
    changeable INT,
    created INT,
    updated INT,
    averageSignal INT,
    geom geometry(Point, 4326)
);

CREATE INDEX towers_geom_idx ON towers USING GIST (geom);

CREATE TABLE ookla_tiles (
    quadkey VARCHAR(20) PRIMARY KEY,
    avg_d_kbps INT,
    avg_u_kbps INT,
    avg_lat_ms INT,
    tests INT,
    devices INT,
    geom geometry(Polygon, 4326)
);

CREATE INDEX ookla_tiles_geom_idx ON ookla_tiles USING GIST (geom);
