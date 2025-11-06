package com.personal.image_toolkit;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * This is the main entry point for the Spring Boot application.
 * The @SpringBootApplication annotation enables the web server,
 * component scanning, and all of Spring's auto-configuration.
 */
@SpringBootApplication
public class ImageToolkitApiApplication {

	public static void main(String[] args) {
		// This one line starts the entire application.
		SpringApplication.run(ImageToolkitApiApplication.class, args);
	}

}